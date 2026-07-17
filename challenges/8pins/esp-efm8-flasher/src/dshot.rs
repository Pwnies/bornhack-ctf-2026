use dshot_frame::NormalFrame;

use esp_hal::rmt::{TxChannelConfig, TxChannelCreator as _};

use esp_hal::gpio::{AnyPin, Level};

use esp_hal::Async;
use esp_hal::rmt::{Rmt, PulseCode};
use esp_hal::time::Rate;

const SHORT: u16 = 89;
const LONG: u16 = 2*SHORT;

const BIT_0: PulseCode = PulseCode::new(Level::High, SHORT, Level::Low, LONG);
const BIT_1: PulseCode = PulseCode::new(Level::High, LONG, Level::Low, SHORT);

pub struct RmtDShot300<'rmt>(Rmt<'rmt, Async>);

impl<'rmt> RmtDShot300<'rmt> {
    pub fn new(rmt: esp_hal::peripherals::RMT<'rmt>) -> Self {
        Self(Rmt::new(rmt, Rate::from_mhz(80)).unwrap().into_async())
    }

    pub async fn send_bits(&mut self, pin: AnyPin<'_>, bits: u16) -> Result<(), esp_hal::rmt::Error> {
        let config = TxChannelConfig::default().with_clk_divider(1).with_idle_output(true).with_idle_output_level(Level::Low);
        let mut channel = self.0.channel0.reborrow().configure_tx(&config).unwrap().with_pin(pin);
        let mut pulsecode: [PulseCode; 17] = [PulseCode(0); 17];
        for i in 0..16 {
            pulsecode[i] = if ((bits << i) & 0x8000) != 0 {
                BIT_1
            } else {
                BIT_0
            };
        }
        channel.transmit(&pulsecode).await
    }

    pub async fn send_frame(&mut self, pin: AnyPin<'_>, frame: NormalFrame) -> Result<(), esp_hal::rmt::Error> {
        self.send_bits(pin, frame.inner()).await
    }
}
