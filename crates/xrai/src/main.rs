use std::env;
use std::ffi::OsStr;
use std::io::{self, Write};
use std::process::ExitCode;

const HELP: &str = "xrai — development scaffold\n\n\
Usage: xrai [OPTION]\n\n\
Options:\n\
  -h, --help       Print help\n\
  -V, --version    Print version and platform\n";

fn main() -> ExitCode {
    let mut args = env::args_os().skip(1);
    let first = args.next();

    let output = if args.next().is_some() {
        None
    } else {
        match first.as_deref() {
            None => Some(HELP.to_owned()),
            Some(arg) if arg == OsStr::new("--help") || arg == OsStr::new("-h") => {
                Some(HELP.to_owned())
            }
            Some(arg) if arg == OsStr::new("--version") || arg == OsStr::new("-V") => {
                Some(format!(
                    "xrai {} ({}-{})\n",
                    env!("CARGO_PKG_VERSION"),
                    env::consts::ARCH,
                    env::consts::OS,
                ))
            }
            Some(_) => None,
        }
    };

    match output {
        Some(output) => match io::stdout().lock().write_all(output.as_bytes()) {
            Ok(()) => ExitCode::SUCCESS,
            Err(error) => {
                let _ = writeln!(io::stderr().lock(), "xrai: could not write output: {error}");
                ExitCode::FAILURE
            }
        },
        None => {
            let _ = writeln!(
                io::stderr().lock(),
                "xrai: unsupported arguments; use --help for available options"
            );
            ExitCode::from(2)
        }
    }
}
