#![no_std]
#![no_main]

use embassy_executor::Spawner;
use esp_backtrace as _;
use esp_hal::uart::{self, Uart};
use esp_hal::usb_serial_jtag::UsbSerialJtag;
use esp_hal::{Config, timer::timg::TimerGroup};
use esp_hal::interrupt::software::SoftwareInterruptControl;
use esp_hal::gpio::{Flex, Input, InputConfig, Level, Output, OutputConfig};

use crate::c2::C2;
use crate::console::Console;
use crate::dshot::RmtDShot300;

mod c2;
mod ihex;
mod dshot;

mod console;
mod app;

esp_bootloader_esp_idf::esp_app_desc!();

#[esp_rtos::main]
pub async fn main(_spawner: Spawner) -> ! {
    let p = esp_hal::init(Config::default());
    let sw_int = SoftwareInterruptControl::new(p.SW_INTERRUPT);
    let timg0 = TimerGroup::new(p.TIMG0);

    esp_rtos::start(timg0.timer0, sw_int.software_interrupt0);
    esp_println::logger::init_logger_from_env();

    let c2ck = Output::new(p.GPIO5, Level::High, OutputConfig::default());
    let c2d = Flex::new(p.GPIO6);

    let uart_config: uart::Config = uart::Config::default().with_baudrate(38400);

    let uart = Uart::new(p.UART0, uart_config).unwrap().with_rx(p.GPIO21).with_tx(p.GPIO20).into_async();

    let app = app::App {
        led: Output::new(p.GPIO8, Level::High, OutputConfig::default()),
        btn: Input::new(p.GPIO9, InputConfig::default()),
        c2: C2::new(c2ck, c2d, esp_hal::delay::Delay::new(), embassy_time::Delay, 1000),
        uart: uart,
        rmt: RmtDShot300::new(p.RMT),
        motor_pins: [
            ("M1", p.GPIO0.into()),
            ("M2", p.GPIO1.into()),
            ("M3", p.GPIO2.into()),
            ("M4", p.GPIO3.into()),
        ]
    };

    let uart = UsbSerialJtag::new(p.USB_DEVICE).into_async();
    let mut console = Console::<_, _, 128, 10>::new(app, uart);
    loop {
        console.run().await;
        log::info!("Lol, console exited. There is no escape");
    }
}
