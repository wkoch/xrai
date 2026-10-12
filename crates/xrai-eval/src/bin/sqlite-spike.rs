//! Development-only experiment driver; unrelated to the installed xrai CLI.
use std::{env, path::Path, time::Instant};
use xrai_eval::sqlite_spike::{self as spike, Reader, Result};

fn run() -> Result<()> {
    let args: Vec<_> = env::args_os().skip(1).collect();
    if args.len() == 3 && args[0] == "hold-uncommitted" {
        return spike::hold_uncommitted(Path::new(&args[1]), Path::new(&args[2]));
    }
    if args.len() == 2 && args[0] == "storage-cost" {
        return storage_cost(Path::new(&args[1]));
    }
    if args.len() != 2 || args[0] != "demonstrate" {
        return Err("usage: sqlite-spike <demonstrate|storage-cost> <new-directory>".into());
    }
    let dir = Path::new(&args[1]);
    std::fs::create_dir(dir)?;
    let path = dir.join("derived.sqlite");
    let mut writer = spike::initialize(&path)?;
    spike::publish(&mut writer, "A", &[spike::document_a()])?;
    let reader1 = Reader::begin(&path)?;
    let reader2 = Reader::begin(&path)?;
    spike::publish(&mut writer, "B", &[spike::document_b()])?;
    assert_eq!(reader1.facts()?[0].name, "OldWidget");
    assert_eq!(reader2.facts()?[0].name, "OldWidget");
    let new_reader = Reader::begin(&path)?;
    assert_eq!(new_reader.generation(), "B");
    assert!(new_reader.search("OldWidget", false)?.is_empty());
    assert_eq!(new_reader.search("NewWidget", false)?.len(), 1);
    let sqlite: String = writer.query_row("SELECT sqlite_version()", [], |r| r.get(0))?;
    let fts5: bool =
        writer.query_row("SELECT sqlite_compileoption_used('ENABLE_FTS5')", [], |r| {
            r.get(0)
        })?;
    assert!(fts5);
    let blobs: i64 = writer.query_row("SELECT sum(length(bytes)) FROM blobs", [], |r| r.get(0))?;
    let pages: i64 = writer.pragma_query_value(None, "page_count", |r| r.get(0))?;
    let page_size: i64 = writer.pragma_query_value(None, "page_size", |r| r.get(0))?;
    spike::backup(&writer, &dir.join("backup.sqlite"))?;
    drop(reader1);
    drop(reader2);
    drop(new_reader);
    writer.execute_batch("PRAGMA wal_checkpoint(TRUNCATE)")?;
    println!(
        "{{\"sqlite\":\"{sqlite}\",\"fts5\":{fts5},\"old_readers\":2,\"old_generation\":\"A\",\"new_generation\":\"B\",\"source_blob_bytes\":{blobs},\"page_count\":{pages},\"page_size\":{page_size},\"database_bytes\":{},\"backup_bytes\":{}}}",
        std::fs::metadata(&path)?.len(),
        std::fs::metadata(dir.join("backup.sqlite"))?.len()
    );
    Ok(())
}

fn storage_cost(dir: &Path) -> Result<()> {
    std::fs::create_dir(dir)?;
    let mut measurements = Vec::new();
    for size in [1024, 65536, 1048576] {
        for changed in [false, true] {
            // Controlled ASCII payload: source storage/FTS overhead, not a
            // real-repository latency, compression or memory benchmark.
            let bytes = b"fn Widget() { return 17; }\n"
                .iter()
                .copied()
                .cycle()
                .take(size)
                .collect::<Vec<_>>();
            let mut new_bytes = bytes.clone();
            if changed {
                new_bytes[0] = b'X';
            }
            let path = dir.join(format!("{size}-{changed}.sqlite"));
            let mut writer = spike::initialize(&path)?;
            let started = Instant::now();
            let mut doc = spike::Document {
                path: "src/widget.rs",
                name: "Widget",
                bytes: &bytes,
                start_byte: 0,
                end_byte: size,
            };
            spike::publish(&mut writer, "A", &[doc.clone()])?;
            doc.bytes = &new_bytes;
            spike::publish(&mut writer, "B", &[doc])?;
            let publication_micros = started.elapsed().as_micros();
            let retained_blobs: i64 =
                writer.query_row("SELECT count(*) FROM blobs", [], |r| r.get(0))?;
            let retained_bytes: i64 =
                writer.query_row("SELECT sum(length(bytes)) FROM blobs", [], |r| r.get(0))?;
            let wal_bytes =
                std::fs::metadata(path.with_file_name(format!("{size}-{changed}.sqlite-wal")))?
                    .len();
            writer.execute_batch("PRAGMA wal_checkpoint(TRUNCATE)")?;
            measurements.push(format!("{{\"source_bytes_per_generation\":{size},\"changed\":{changed},\"retained_blob_count\":{retained_blobs},\"retained_blob_bytes\":{retained_bytes},\"database_bytes_after_checkpoint\":{},\"wal_bytes_before_checkpoint\":{wal_bytes},\"publication_micros\":{publication_micros}}}",std::fs::metadata(&path)?.len()));
        }
    }
    println!("[{}]", measurements.join(","));
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
