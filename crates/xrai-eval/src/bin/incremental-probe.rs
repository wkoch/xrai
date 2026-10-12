//! Development inventory probe for harness A→B events, not a retrieval index.
use std::io::{self, BufRead, Write};
use std::path::Path;
use xrai_eval::filesystem_spike::{Config, inventory};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = std::env::args().skip(1);
    let root = args.next().ok_or("usage: incremental-probe ROOT")?;
    if args.next().is_some() {
        return Err("usage: incremental-probe ROOT".into());
    }
    let mut current = None;
    for line in io::stdin().lock().lines() {
        match line?.as_str() {
            "INDEX" | "UPDATE" => current = Some(inventory(Path::new(&root), &Config::default())?),
            "QUERY" => (),
            "QUIT" => break,
            _ => return Err("unknown command".into()),
        }
        let state = current.as_ref().ok_or("INDEX required")?;
        for source in &state.sources {
            let hex: String = source
                .path
                .iter()
                .map(|byte| format!("{byte:02x}"))
                .collect();
            println!("SOURCE\t{hex}\t{}", source.hash);
        }
        for diagnostic in &state.diagnostics {
            println!("DIAGNOSTIC\t{diagnostic:?}");
        }
        println!("END\t{}\t{}", std::process::id(), state.checkout_id);
        io::stdout().flush()?;
    }
    Ok(())
}
