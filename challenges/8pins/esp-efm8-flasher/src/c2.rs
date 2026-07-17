#![allow(unused)]

use critical_section::CriticalSection;

use esp_hal::gpio::OutputConfig;

use esp_hal::gpio::Flex;

use esp_hal::gpio::Output;
use esp_hal::time::Instant;

use embedded_hal::delay::DelayNs as BlockingDelayTrait;
use embedded_hal_async::delay::DelayNs as AsyncDelayTrait;

use crate::ihex::IHexError;
use crate::ihex::IHexRecord;

pub const DEVICEID: u8 = 0x00;
pub const REVID: u8 = 0x01;
pub const FPCTL: u8 = 0x02;
pub const FPDAT: u8 = 0xb4;

pub const ADDRESS_INBUSY: u8 = 0x02;
pub const ADDRESS_OUTREADY: u8 = 0x01;
pub const ADDRESS_FLASH_BUSY: u8 = 0x80;
pub const ADDRESS_FLASH_ERROR: u8 = 0x40;

pub const PI_SFR_READ: u8 = 0x09;
pub const PI_SFR_WRITE: u8 = 0x0a;
pub const PI_FLASH_ERASE: u8 = 0x03;
pub const PI_FLASH_READ: u8 = 0x06;
pub const PI_FLASH_WRITE: u8 = 0x07;

trait ToBits<const N: usize> {
    fn to_bits(&self) -> [bool; N];
}

trait FromBits<const N: usize> {
    fn from_bits(bits: [bool; N]) -> Self;
}

impl ToBits<8> for u8 {
    fn to_bits(&self) -> [bool; 8] {
        core::array::from_fn(|i| ((self >> i) & 1) == 1)
    }
}

impl FromBits<8> for u8 {
    fn from_bits(bits: [bool; 8]) -> Self {
        bits.into_iter().enumerate().map(|(i, bit)| (bit as Self) << i).sum()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum C2Error {
    TimeoutError,
    StatusError(u8)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum IHexFlashError {
    C2Error(C2Error),
    IHexError(IHexError),
}

impl From<C2Error> for IHexFlashError {
    fn from(value: C2Error) -> Self {
        IHexFlashError::C2Error(value)
    }
}

impl From<IHexError> for IHexFlashError {
    fn from(value: IHexError) -> Self {
        IHexFlashError::IHexError(value)
    }
}

pub struct C2<'a, BlockingDelay: BlockingDelayTrait, AsyncDelay: AsyncDelayTrait> {
    c2ck: Output<'a>,
    c2d: Flex<'a>,
    timeout: u32,
    blocking_delay: BlockingDelay,
    async_delay: AsyncDelay,
}

impl<'a, BlockingDelay: BlockingDelayTrait, AsyncDelay: AsyncDelayTrait> C2<'a, BlockingDelay, AsyncDelay> {
    pub fn new(c2ck: Output<'a>, mut c2d: Flex<'a>, blocking_delay: BlockingDelay, async_delay: AsyncDelay, timeout: u32) -> Self {
        c2d.set_input_enable(true);
        c2d.apply_output_config(&OutputConfig::default());
        Self {
            c2ck, c2d,
            timeout,
            blocking_delay,
            async_delay
        }
    }

    pub async fn reset(&mut self) {
        self.c2ck.set_low();
        self.async_delay.delay_us(20).await;
        self.c2ck.set_high();
        self.async_delay.delay_us(2).await;
    }

    pub async fn clock_strobe(&mut self) {
        self.blocking_delay.delay_ns(40);
        {
            // This timing is critical, holding c2ck low for too long causes reset of EFM8 MCU as c2ck pin is shared with RST
            // Thus we take a CriticalSection and use a BLOCKING delay.
            // Interrupts will not get handled for 100ns.
            let _cs = unsafe { CriticalSection::new() };
            self.c2ck.set_low();
            self.blocking_delay.delay_ns(100); 
            self.c2ck.set_high();
        }
        self.blocking_delay.delay_ns(120);
    }

    pub async fn shift_out_bits(&mut self, bits: &[bool]) {
        for &bit in bits {
            self.c2d.set_level(bit.into());
            self.clock_strobe().await;
        }
    }

    pub async fn shift_in_bits<const N: usize>(&mut self) -> [bool; N] {
        let mut bits = [false; N];
        for bit in bits.iter_mut() {
            self.clock_strobe().await;
            *bit = self.c2d.is_high()
        }
        bits
    }

    pub async fn write_address(&mut self, address: u8) {
        self.clock_strobe().await; // START
        self.c2d.set_output_enable(true);
        self.shift_out_bits(&[true, true]).await; // INS 0-1
        self.shift_out_bits(&address.to_bits()).await; // ADDRESS 0-7
        self.c2d.set_output_enable(false);
        self.clock_strobe().await; // STOP
    }

    pub async fn read_address(&mut self) -> u8 {
        self.clock_strobe().await; // START
        self.c2d.set_output_enable(true);
        self.shift_out_bits(&[false, true]).await; // INS 0-1
        self.c2d.set_output_enable(false);
        let bits = self.shift_in_bits().await;
        self.clock_strobe().await; // STOP
        u8::from_bits(bits)
    }

    pub async fn wait_for_ack(&mut self) -> Result<(), C2Error> {
        self.clock_strobe().await; // WAIT
        let mut i = 0;
        while self.c2d.is_low(){
            // self.async_delay.delay_ns(10).await;
            self.clock_strobe().await;
            i += 1;
            if i > self.timeout {
                return Err(C2Error::TimeoutError)
            }
        }
        log::trace!("{i} Wait cycles");
        Ok(())
    }

    pub async fn write_data8(&mut self, data: u8) -> Result<(), C2Error> {
        self.clock_strobe().await; // START
        self.c2d.set_output_enable(true);
        self.shift_out_bits(&[true, false, false, false]).await; // INS 0-1 LENGTH 0-1
        self.shift_out_bits(&data.to_bits()).await; // DATA 0-7
        self.c2d.set_output_enable(false);
        self.wait_for_ack().await?; // WAIT
        self.clock_strobe().await; // STOP

        Ok(())
    }

    pub async fn read_data8(&mut self) -> Result<u8, C2Error> {
        self.clock_strobe().await; // START
        self.c2d.set_output_enable(true);
        self.shift_out_bits(&[false, false, false, false]).await; // INS 0-1 Length 0-1
        self.c2d.set_output_enable(false);
        self.wait_for_ack().await?; // WAIT
        let bits = self.shift_in_bits().await; // DATA 0-7
        self.clock_strobe().await; // STOP
        Ok(u8::from_bits(bits))
    }

    pub async fn poll_bit_high(&mut self, mask: u8) -> Result<u8, C2Error> {
        for _ in 0..self.timeout {
            let address = self.read_address().await;
            if (address & mask) != 0x00 {
                return Ok(address)
            }
        }
        Err(C2Error::TimeoutError)
    }

    pub async fn poll_bit_low(&mut self, mask: u8) -> Result<u8, C2Error> {
        for _ in 0..self.timeout {
            let address = self.read_address().await;
            if (address & mask) == 0x00 {
                return Ok(address)
            }
        }
        Err(C2Error::TimeoutError)
    }

    pub async fn read_reg_u8(&mut self, address: u8) -> Result<u8, C2Error> {
        self.write_address(address).await;
        self.read_data8().await
    }

    pub async fn write_reg_u8(&mut self, address: u8, data: u8) -> Result<(), C2Error> {
        self.write_address(address).await;
        self.write_data8(data).await?;
        Ok(())
    }

    pub async fn init_pi(&mut self) -> Result<(), C2Error> {
        // self.reset().await;
        self.write_address(FPCTL).await;
        self.write_data8(0x02).await?;
        self.write_data8(0x04).await?;
        self.write_data8(0x01).await?;
        self.async_delay.delay_ms(20).await;
        Ok(())
    }

    pub async fn pi_write_byte(&mut self, byte: u8) -> Result<(), C2Error> {
        self.write_data8(byte).await?;
        self.poll_bit_low(ADDRESS_INBUSY).await?;
        Ok(())
    }

    pub async fn pi_write_slice(&mut self, bytes: &[u8]) -> Result<(), C2Error> {
        for &byte in bytes.iter() {
            self.pi_write_byte(byte).await?;
        }
        Ok(())
    }

    pub async fn pi_read_byte(&mut self) -> Result<u8, C2Error> {
        self.poll_bit_high(ADDRESS_OUTREADY).await?;
        self.read_data8().await
    }

    pub async fn pi_read_slice(&mut self, bytes: &mut [u8]) -> Result<(), C2Error> {
        for byte in bytes.iter_mut() {
            *byte  = self.pi_read_byte().await?;
        }
        Ok(())
    }

    pub async fn pi_read_and_check_status(&mut self) -> Result<(), C2Error> {
        let status = self.pi_read_byte().await?;
        if status != 0x0d {
            return Err(C2Error::StatusError(status))
        }
        Ok(())
    }

    pub async fn read_sfr(&mut self, address: u8) -> Result<u8, C2Error> {
        log::debug!("Reading SFR register {address:02x}");
        self.write_address(FPDAT).await;
        self.pi_write_byte(PI_SFR_READ).await?;

        self.pi_read_and_check_status().await?;

        self.pi_write_byte(address).await?;
        self.pi_write_byte(0x01).await?;
        self.pi_read_byte().await
    }

    pub async fn write_sfr(&mut self, address: u8, value: u8) -> Result<(), C2Error> {
        log::debug!("Reading SFR register {address:02x}");
        self.write_address(FPDAT).await;

        self.pi_write_byte(PI_SFR_WRITE).await?;

        self.pi_read_and_check_status().await?;

        self.pi_write_byte(address).await?;
        self.pi_write_byte(0x01).await?;
        self.pi_write_byte(value).await?;
        Ok(())
    }

    pub async fn read_flash_block(&mut self, addr: u16, block: &mut [u8]) -> Result<(), C2Error> {
        log::debug!("Reading flash block");

        let start = Instant::now();

        self.write_address(FPDAT).await;
        self.pi_write_byte(PI_FLASH_READ).await?;
        self.pi_read_and_check_status().await?;
        self.pi_write_slice(&addr.to_be_bytes()).await?;
        self.pi_write_byte(block.len() as u8).await?;
        self.pi_read_and_check_status().await?;
        self.pi_read_slice(block).await?;

        log::debug!("Read operation took {} ns", start.elapsed().as_millis());

        Ok(())
    }

    pub async fn write_flash_block(&mut self, addr: u16, block: &[u8]) -> Result<(), C2Error> {
        log::debug!("Writing Flash");

        let start = Instant::now();

        self.write_address(FPDAT).await;
        self.pi_write_byte(PI_FLASH_WRITE).await?;
        self.pi_read_and_check_status().await?;
        self.pi_write_slice(&addr.to_be_bytes()).await?;
        self.pi_write_byte(block.len() as u8).await?;
        self.pi_write_slice(block).await?;
        self.pi_read_and_check_status().await?;

        log::debug!("Write operation took {} ms", start.elapsed().as_millis());

        Ok(())
    }

    pub async fn erase_flash(&mut self) -> Result<(), C2Error> {
        log::debug!("Erasing Flash");

        let start = Instant::now();

        self.write_address(FPDAT).await;
        self.pi_write_byte(PI_FLASH_ERASE).await?;
        self.pi_read_and_check_status().await?;
        self.pi_write_slice(&[0xde, 0xad, 0xa5]).await?;

        log::debug!("Waiting for flash erase to finish");

        loop {
            let address = self.read_address().await;
            if (address & ADDRESS_FLASH_BUSY) == 0x00 {
                break;
            }
            // self.async_delay.delay_ns(1).await;
        }

        self.pi_read_and_check_status().await?;

        log::debug!("Erase operation took {} ms", start.elapsed().as_millis());

        Ok(())
    }

    pub async fn flash_ihex(&mut self, ihex: &str) -> Result<(), IHexFlashError> {
        let start = Instant::now();

        for line in ihex.lines() {
            let record = line.parse::<IHexRecord>()?;
            if record.record_type == 0x00 {
                log::debug!("Writing {:04x} {:02x?}", record.address, record.data);
                self.write_flash_block(record.address, &record.data).await?;
            }
        }

        log::info!("Flash Write took {} ms", start.elapsed().as_millis());

        Ok(())
    }
}
