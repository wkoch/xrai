use std::io::{Read, Write};
use xrai_eval::tsjs_semantics::{Input, build};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut bytes = Vec::new();
    std::io::stdin()
        .take(8 * 1024 * 1024 + 1)
        .read_to_end(&mut bytes)?;
    if bytes.len() > 8 * 1024 * 1024 {
        return Err("input exceeds 8 MiB".into());
    }
    let input: Input = serde_json::from_slice(&bytes)?;
    let snapshot = build(input)?;
    serde_json::to_writer(std::io::stdout().lock(), &snapshot)?;
    std::io::stdout().write_all(b"\n")?;
    Ok(())
}
