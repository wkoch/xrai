use std::{
    env,
    io::{self, Read},
    process::ExitCode,
};
use xrai_eval::parsing_spike;

fn run() -> parsing_spike::Result<bool> {
    let args: Vec<_> = env::args().skip(1).collect();
    if args.len() == 3 && args[0] == "isolation-check" {
        let port: u16 = args[2].parse()?;
        let network_blocked = std::net::TcpStream::connect_timeout(
            &std::net::SocketAddr::from(([127, 0, 0, 1], port)),
            std::time::Duration::from_millis(200),
        )
        .is_err();
        let other_executable_blocked = std::process::Command::new("/bin/sh")
            .args(["-c", "exit 0"])
            .output()
            .is_err();
        let evaluator_file_blocked = std::fs::read(&args[1]).is_err();
        println!(
            "{{\"network_blocked\":{network_blocked},\"other_executable_blocked\":{other_executable_blocked},\"evaluator_file_blocked\":{evaluator_file_blocked}}}"
        );
        return Ok(network_blocked && other_executable_blocked && evaluator_file_blocked);
    }
    if args == ["inventory"] {
        println!("{}", parsing_spike::inventory()?);
        return Ok(true);
    }
    if args.len() != 2 || args[0] != "parse" {
        return Err("usage: parsing-spike inventory | parsing-spike parse <rust|javascript|jsx|typescript|tsx|python|go> (source on stdin)".into());
    }
    let mut source = Vec::new();
    io::stdin().read_to_end(&mut source)?;
    let parsed = parsing_spike::parse(&args[1], &source)?;
    println!("{}", parsed.json(&args[1]));
    Ok(parsed.complete)
}
fn main() -> ExitCode {
    match run() {
        Ok(true) => ExitCode::SUCCESS,
        Ok(false) => ExitCode::from(2),
        Err(error) => {
            eprintln!("{error}");
            ExitCode::from(1)
        }
    }
}
