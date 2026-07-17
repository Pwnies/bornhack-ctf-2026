use embedded_io_async::{Read, Write};
use heapless::{String, Vec};

pub async fn readline<Io: Read + Write, const N: usize>(io: &mut Io, prompt: &str, history: &[String<N>]) -> Result<heapless::String<N>, Io::Error> {
    let mut current = heapless::String::new();
    let mut s = heapless::String::new();

    let mut history_index = history.len();

    io.write(prompt.as_bytes()).await?;
    loop {
        history_index = history_index.min(history.len());

        let mut byte = 0u8;
        io.read(core::slice::from_mut(&mut byte)).await?;
        if byte == 0x08 {
            if s.pop().is_some() {
                io.write_all(b"\x08 \x08").await?;
            }
            continue;
        }
        if byte == 0x1b {
            // ESCAPE
            io.read(core::slice::from_mut(&mut byte)).await?;
            if byte == b'[' {
                io.read(core::slice::from_mut(&mut byte)).await?;
                match byte {
                    b'A' => {
                        if history_index == history.len() {
                            current = s;
                        }
                        history_index = history_index.saturating_sub(1);
                        s = history.get(history_index).cloned().unwrap_or_default();

                        io.write(b"\r\x1b[K").await?;
                        io.write(prompt.as_bytes()).await?;
                        io.write(s.as_bytes()).await?;
                    }
                    b'B' => {
                        history_index += 1;
                        if history_index < history.len() {
                            s = history[history_index].clone()
                        } else {
                            s = current.clone();
                        }
                        io.write(b"\r\x1b[K").await?;
                        io.write(prompt.as_bytes()).await?;
                        io.write(s.as_bytes()).await?;
                    }
                    _ => {}
                }
            }
            continue;
        }
        if byte == b'\r' || byte == b'\n' {
            io.write_all(b"\r\n").await?;
            break;
        }
        io.write_all(&[byte]).await?;
        if s.push(byte.into()).is_err() {
            break;
        }
    }
    Ok(s)
}

pub trait AppTrait {
    type Error<'argv>: core::fmt::Debug;

    async fn handle_command<'argv, Io: Read + Write>(&mut self, io: &mut Io, argv: &[&'argv str]) -> Result<bool, Self::Error<'argv>>;
}

pub struct Console<App, Io: Read + Write, const N: usize, const H: usize>{
    app: App,
    io: Io,
    history: Vec<String<N>, H>,
}

impl<App: AppTrait, Io: Read + Write, const N: usize, const H: usize> Console<App, Io, N, H> {
    pub const fn new(app: App, io: Io) -> Self {
        Self {
            app,
            io,
            history: Vec::new(),
        }
    }

    pub async fn run_command(&mut self, line: &str) -> bool {
        let argv: Vec<&str, 10> = Vec::from_iter(line.split_whitespace());
        match self.app.handle_command(&mut self.io, &argv).await {
            Err(err) => {
                log::info!("Command failed: {err:?}");
                false
            }
            Ok(exit) => exit
        }
    }

    pub async fn run(&mut self) {
        let mut last: Option<String<N>> = None;
        loop {
            let _ = self.io.flush().await;
            let line: String<N> = match readline(&mut self.io, "> ", &self.history).await {
                Ok(line) => line,
                Err(err) => {
                    log::warn!("Failed to read line: {err:?}");
                    continue;
                },
            };
            let line = if line.len() == 0 {
                if let Some(line) = last.take() {
                    line
                } else {
                    continue
                }
            } else {
                if self.history.is_full() {
                    self.history.remove(0);
                }
                let _ = self.history.push(line.clone());
                line
            };
            if self.run_command(&line).await {
                break
            };
            last = Some(line);
        }
    }
}