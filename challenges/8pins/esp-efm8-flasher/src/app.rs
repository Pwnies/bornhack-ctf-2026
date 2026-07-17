use core::num::ParseIntError;

use dshot_frame::{Command, NormalFrame};
use embassy_futures::select::{Either, select};
use embassy_time::Timer;
use embedded_io_async::{Read, Write};
use esp_hal::{Async, gpio::{AnyPin, Input, Output}, uart::{self, RxError, Uart}};
use heapless::Vec;

use crate::{c2::{self, C2}, console::{self, AppTrait}, dshot::RmtDShot300};

#[derive(Debug, Clone)]
#[allow(unused)]
pub enum AppError<'a> {
    TooShort,
    InvalidCommand(&'a str),
    InvalidArgument,
    Message(&'static str),
    Io,
}

impl<'a> From<ParseIntError> for AppError<'a> {
    fn from(_: ParseIntError) -> Self {
        AppError::InvalidArgument
    }
}

#[allow(unused)]
pub struct App {
    pub led: Output<'static>,
    pub btn: Input<'static>,
    pub c2: C2<'static, esp_hal::delay::Delay, embassy_time::Delay>,
    pub uart: Uart<'static, Async>,
    pub rmt: RmtDShot300<'static>,
    pub motor_pins: [(&'static str, AnyPin<'static>); 4]
}
// static FIRMWARE_BYTES: &'static [u8] = include_bytes!("../E_X_50_24_v0.21.1-RC1.hex");
// static FIRMWARE_BYTES: &'static [u8] = include_bytes!("../blinky.ihx");
static FIRMWARE_BYTES: &'static [u8] = &[];

impl AppTrait for App {
    type Error<'argv> = AppError<'argv>;

    async fn handle_command<'argv, Io: Read + Write>(&mut self, io: &mut Io, argv: &[&'argv str]) -> Result<bool, Self::Error<'argv>> {
        let (&cmd, args) = argv.split_first().ok_or(AppError::TooShort)?;

        self.led.set_low();

        let res = match cmd {
            "repeat" => self.cmd_repeat(io, args).await,
            "retry" => self.cmd_retry(io, args).await,
            "flash" => self.handle_simple_command(io, &["c2", "--reset", "flash"]).await,
            "ihex" => self.handle_simple_command(io, &["c2", "--reset", "ihex"]).await,
            _ => self.handle_simple_command(io, argv).await,
        };

        self.led.set_high();

        Ok(false)
    }
}

impl App {
    async fn handle_simple_command<'argv, Io: Read + Write>(&mut self, io: &mut Io, argv: &[&'argv str]) -> Result<(), AppError<'argv>> {
        let (&cmd, args) = argv.split_first().ok_or(AppError::TooShort)?;
        match cmd {
            "c2" => self.cmd_c2(io, args).await,
            "motor" => self.cmd_motor(args).await,
            "uart" => self.cmd_uart(io, args).await,
            "reboot" => esp_hal::rom::software_reset(),
            cmd => Err(AppError::InvalidCommand(cmd)),
        }
    }

    pub async fn cmd_repeat<'args, Io: Read + Write>(&mut self, io: &mut Io, args: &[&'args str]) -> Result<(), AppError<'args>> {
        let (times_str, args) = args.split_first().ok_or(AppError::TooShort)?;
        let times = u32::from_str_radix(times_str, 10)?;
        let (delay_str, argv) = args.split_first().ok_or(AppError::TooShort)?;
        let delay = u64::from_str_radix(delay_str, 10)?;

        for i in 0..times {
            log::info!("Repeat: {i}: {args:?}");
            self.handle_simple_command(io, argv).await?;
            Timer::after_millis(delay).await;
        }
        Ok(())
    }

    pub async fn cmd_retry<'args, Io: Read + Write>(&mut self, io: &mut Io, args: &[&'args str]) -> Result<(), AppError<'args>> {
        let (times_str, args) = args.split_first().ok_or(AppError::TooShort)?;
        let times = u32::from_str_radix(times_str, 10)?;
        let (delay_str, argv) = args.split_first().ok_or(AppError::TooShort)?;
        let delay = u64::from_str_radix(delay_str, 10)?;

        for i in 0..times {
            log::info!("Repeat: {i}: {args:?}");
            match self.handle_simple_command(io, argv).await {
                Ok(()) => {
                    break;
                }
                Err(err) => {
                    log::info!("Command failed: {err:?}");
                    Timer::after_millis(delay).await;
                    log::info!("Retrying {i}: {argv:?}");
                }
            };
        }

        Ok(())
    }

    pub async fn cmd_c2<'args, Io: Read + Write>(&mut self, io: &mut Io, mut args: &[&'args str]) -> Result<(), AppError<'args>> {
        let firmware_ihex = str::from_utf8(FIRMWARE_BYTES).unwrap();

        let mut wait_for_connect = false;
        let mut reset_before = false;
        let mut reset_after = false;

        while let Some((&arg, rest)) = args.split_first() {
            match arg {
                "--wait" => {
                    wait_for_connect = true;
                }
                "--reset" => {
                    reset_after = true;
                    reset_before = true;
                }
                "--reset-after" => {
                    reset_after = true;
                }
                "--reset-before" => {
                    reset_before = true;
                }
                _ => {
                    break
                }
            }
            args = rest;
        }

        let (&subcmd, args) = args.split_first().ok_or(AppError::TooShort)?;

        if reset_before {
            log::info!("Resetting C2 PI interface");
            self.c2.reset().await;
        }

        if wait_for_connect {
            log::info!("Waiting for connection!");
            for _ in 0..100 {
                if self.c2.init_pi().await.is_ok() {
                    break;
                }
                Timer::after_millis(100).await;
            }
        }

        log::info!("Initializing C2 PI interface");
        let _ = self.c2.init_pi().await;

        match subcmd {
            "id" => {
                log::info!("C2 deviceid: {:x?}", self.c2.read_reg_u8(c2::DEVICEID).await);
                log::info!("C2 revid: {:x?}", self.c2.read_reg_u8(c2::REVID).await);
            },
            "uid" => {
                let mut uid = [0u8; 16];
                log::info!("Flash Read: {:?}", self.c2.read_flash_block(0xffc0, &mut uid).await);
                log::info!("EFM8 UID: {:02x?}", uid);
            }
            "erase" => {
                log::info!("Flash Erase: {:?}", self.c2.erase_flash().await);
            }
            "write" => {
                log::info!("Flash Write: {:?}", self.c2.flash_ihex(firmware_ihex).await);
            }
            "flash" => {
                log::info!("Flash Erase: {:?}", self.c2.erase_flash().await);
                log::info!("Flash Write: {:?}", self.c2.flash_ihex(firmware_ihex).await);
            }
            "reset" => {
                log::info!("Resetting C2 PI interface");
                self.c2.reset().await;
            }
            "ihex" => {
                log::info!("Falsh Erase: {:?}", self.c2.erase_flash().await);
                log::info!("Send IHEX, stop with empty line");
                loop {
                    let line = match console::readline::<Io, 600>(io, "ihex>", &[]).await {
                        Ok(line) => line,
                        Err(err) => {
                            log::warn!("faile to readline: {:?}", err);
                            break;
                        }
                    };
                    let line = line.trim();
                    if line.is_empty() {
                        break;
                    }
                    log::debug!("{:?}", self.c2.flash_ihex(line).await);
                }
            }
            "read" => {
                let (&address_str, args) = args.split_first().ok_or(AppError::TooShort)?;
                let address = u16::from_str_radix(address_str, 16)?;
                let (&length_str, _rest) = args.split_first().ok_or(AppError::TooShort)?;
                let length = u16::from_str_radix(length_str, 16)?;
                for offset in (0..length).step_by(16) {
                    let mut block = [0u8; 16];
                    let address = address + offset;
                    let length = ((length - offset) as usize).min(block.len());
                    if self.c2.read_flash_block(address, &mut block).await.is_ok() {
                        let block = &block[..length];
                        log::info!("{address:04x}: {block:02x?}");
                    } else {
                        log::warn!("Failed to read block at {address:04}");
                    }
                }
            }
            "sfr_read" => {
                let (&address_str, _args) = args.split_first().ok_or(AppError::TooShort)?;
                let address = u8::from_str_radix(address_str, 16)?;
                log::info!("SFR {address:02x}: {:02x?}", self.c2.read_sfr(address).await);
            }
            subcmd => {
                return Err(AppError::InvalidCommand(subcmd));
            }
        }

        if reset_after {
            log::info!("Resetting C2 PI interface");
            self.c2.reset().await;
        }
    
        Ok(())
    }
    
    pub async fn cmd_motor<'args>(&mut self, args: &[&'args str]) -> Result<(), AppError<'args>> {
        let (&motor_num, args) = args.split_first().ok_or(AppError::TooShort)?;
        let motor_pins = match motor_num {
            "1" => &mut self.motor_pins[0..1],
            "2" => &mut self.motor_pins[1..2],
            "3" => &mut self.motor_pins[2..3],
            "4" => &mut self.motor_pins[3..4],
            "all" => &mut self.motor_pins,
            _ => return Err(AppError::InvalidArgument),
        };
        let (&subcmd, _args) = args.split_first().ok_or(AppError::TooShort)?;
        let frames: Vec<(usize, u64, NormalFrame), 3> = match subcmd {
            "beep1" => Vec::from_array([
                (10, 100, NormalFrame::command(Command::Beep1, false))
            ]),
            "arm" => Vec::from_array([
                (10, 1, NormalFrame::command(Command::SpinDirectionNormal, false)),
                (100, 1, NormalFrame::new(0, false).unwrap()),
            ]),
            speed => {
                let speed = u16::from_str_radix(speed, 10)?;
                Vec::from_array([
                    (10, 1, NormalFrame::new(speed, false).ok_or(AppError::InvalidArgument)?)
                ])
            }
        };

        for (name, pin) in motor_pins.iter_mut() {
            for &(repeat, delay, frame) in frames.iter() {
                let bits = frame.inner();
                log::info!("DSHOT/{name}: Sending {bits:016b} repeat {repeat} delay {delay}");
                for _ in 0..repeat {
                    if let Err(err) = self.rmt.send_frame(pin.reborrow(), frame.clone()).await {
                        log::warn!("Got error while sending frame: {frame:?} {err:?}");
                    }
                    Timer::after_millis(delay).await;
                }
            }
        }
        
        Ok(())
    }

    pub async fn cmd_uart<'args, Io: Read + Write>(&mut self, io: &mut Io, args: &[&'args str]) -> Result<(), AppError<'args>> {
        if let Some((&baudrate_str, _args)) = args.split_first() {
            let baudrate = u32::from_str_radix(baudrate_str, 10)?;
            log::info!("Setting baudrate to {baudrate}");
            self.uart.apply_config(&uart::Config::default().with_baudrate(baudrate)).map_err(|_| AppError::Message("failed to set baudrate"))?;
        }

        loop {
            let mut io_buf = [0u8; 16];
            let mut uart_buf = [0u8; 16];


            match select(io.read(&mut io_buf), self.uart.read_async(&mut uart_buf)).await {
                Either::First(Ok(n)) => {
                    if io_buf[..n].iter().any(|&b| b == 0x04) {
                        return Ok(())
                    }
                    self.uart.write_async(&io_buf[..n]).await.map_err(|_| AppError::Io)?;
                }
                Either::Second(Ok(n)) => {
                    io.write_all(&uart_buf[..n]).await.map_err(|_| AppError::Io)?;
                }
                Either::Second(Err(RxError::FifoOverflowed)) => {
                    log::warn!("FIFO Overflowed!");
                }
                _ => {
                    log::warn!("uuuh error");
                    // return Err(AppError::Io);

                }
            }
        }
    }
}

struct DbgApp<'c2>(&'c2 mut C2<'static, esp_hal::delay::Delay, embassy_time::Delay>);

impl<'c2> AppTrait for DbgApp<'c2> {
    type Error<'argv> = AppError<'argv>;

    async fn handle_command<'argv, Io: Read + Write>(&mut self, io: &mut Io, argv: &[&'argv str]) -> Result<bool, Self::Error<'argv>> {
        let (&cmd, args) = argv.split_first().ok_or(AppError::TooShort)?;

        match cmd {
            "s" | "si" => {
                log::debug!("Single stepping!");
            },
            "exit" => return Ok(true),
            cmd => return Err(AppError::InvalidCommand(cmd))
        }

        Ok(false)
    }
}