use rusqlite::{ErrorCode, TransactionBehavior, params};
use std::{
    fs,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::atomic::{AtomicU64, Ordering},
    time::{Duration, Instant},
};
use xrai_eval::sqlite_spike::{self as spike, Reader, Result};

static NEXT: AtomicU64 = AtomicU64::new(0);
struct Temporary(PathBuf);
impl Temporary {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!(
            "xrai sqlite spike {} {}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).unwrap();
        Self(path)
    }
    fn db(&self) -> PathBuf {
        self.0.join("derived.sqlite")
    }
}
impl Drop for Temporary {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

struct Worker(Child);
impl Drop for Worker {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}
fn crash_writer(database: &Path, ready: &Path) -> Worker {
    Worker(
        Command::new(env!("CARGO_BIN_EXE_sqlite-spike"))
            .args(["hold-uncommitted"])
            .arg(database)
            .arg(ready)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::inherit())
            .spawn()
            .unwrap(),
    )
}
fn wait_ready(worker: &mut Worker, ready: &Path) {
    let deadline = Instant::now() + Duration::from_secs(10);
    while !ready.exists() {
        assert!(
            worker.0.try_wait().unwrap().is_none(),
            "worker died before the transaction handshake"
        );
        assert!(Instant::now() < deadline, "writer handshake timeout");
        std::thread::sleep(Duration::from_millis(10));
    }
}
fn integrity(connection: &rusqlite::Connection) -> Result<()> {
    let result: String = connection.query_row("PRAGMA integrity_check", [], |r| r.get(0))?;
    assert_eq!(result, "ok");
    let violations: i64 =
        connection.query_row("SELECT count(*) FROM pragma_foreign_key_check", [], |r| {
            r.get(0)
        })?;
    assert_eq!(violations, 0);
    Ok(())
}

#[test]
fn two_readers_keep_a_bytes_facts_and_fts_while_writer_publishes_b() -> Result<()> {
    let dir = Temporary::new();
    let path = dir.db();
    let mut writer = spike::initialize(&path)?;
    let wal: String = writer.pragma_query_value(None, "journal_mode", |r| r.get(0))?;
    assert_eq!(wal, "wal");
    spike::publish(&mut writer, "A", &[spike::document_a()])?;
    let a1 = Reader::begin(&path)?;
    let a2 = Reader::begin(&path)?;
    let first = a1.facts()?;
    assert_eq!(first[0].bytes, spike::document_a().bytes);
    assert_eq!(
        first[0].hash,
        blake3::hash(spike::document_a().bytes).to_hex().as_str()
    );
    spike::publish(&mut writer, "B", &[spike::document_b()])?;
    assert_eq!(a1.generation(), "A");
    assert_eq!(a2.generation(), "A");
    assert_eq!(a1.facts()?, first);
    assert_eq!(a2.facts()?, first);
    assert_eq!(a1.search("OldWidget", false)?, ["src/old_widget.rs"]);
    assert!(a2.search("NewWidget", false)?.is_empty());
    let b = Reader::begin(&path)?;
    assert_eq!(b.generation(), "B");
    assert_eq!(b.facts()?[0].bytes, spike::document_b().bytes);
    assert!(b.search("OldWidget", false)?.is_empty());
    assert!(b.search("old_widget", false)?.is_empty());
    assert_eq!(b.search("NewWidget", false)?, ["src/new_widget.rs"]);
    assert_eq!(b.search("name:Widget", true)?, ["src/new_widget.rs"]);
    assert_eq!(b.search("path:new_widget", false)?, ["src/new_widget.rs"]);
    integrity(&writer)?;
    Ok(())
}

#[test]
fn killed_writer_rolls_back_b_keeps_a_and_records_abandoned_staging() -> Result<()> {
    let dir = Temporary::new();
    let path = dir.db();
    let mut writer = spike::initialize(&path)?;
    spike::publish(&mut writer, "A", &[spike::document_a()])?;
    let reader1 = Reader::begin(&path)?;
    let reader2 = Reader::begin(&path)?;
    let ready = dir.0.join("writer-ready");
    let mut worker = crash_writer(&path, &ready);
    wait_ready(&mut worker, &ready);
    assert_eq!(reader1.generation(), "A");
    assert_eq!(reader2.facts()?[0].name, "OldWidget");
    assert_eq!(Reader::begin(&path)?.generation(), "A");
    let start = Instant::now();
    let rejected = writer
        .transaction_with_behavior(TransactionBehavior::Immediate)
        .unwrap_err();
    assert!(
        matches!(rejected,rusqlite::Error::SqliteFailure(error,_) if error.code==ErrorCode::DatabaseBusy)
    );
    assert!(
        start.elapsed() >= Duration::from_millis(100),
        "writer did not wait its declared bounded timeout"
    );
    assert!(
        start.elapsed() < Duration::from_secs(3),
        "writer exceeded test scheduling allowance"
    );
    worker.0.kill()?;
    let status = worker.0.wait()?;
    assert!(!status.success());
    drop(reader1);
    drop(reader2);
    drop(writer);
    let mut reopened = spike::open_existing(&path)?;
    assert_eq!(Reader::begin(&path)?.generation(), "A");
    for table in ["generations", "sources", "facts", "documents", "substrings"] {
        let sql = if table == "generations" {
            "SELECT count(*) FROM generations WHERE id='B'".to_owned()
        } else {
            format!("SELECT count(*) FROM {table} WHERE generation='B'")
        };
        assert_eq!(reopened.query_row(&sql, [], |r| r.get::<_, i64>(0))?, 0);
    }
    let b_hash = blake3::hash(spike::document_b().bytes).to_hex().to_string();
    assert_eq!(
        reopened.query_row("SELECT count(*) FROM blobs WHERE hash=?1", [b_hash], |r| {
            r.get::<_, i64>(0)
        })?,
        0
    );
    let pending: String = reopened.query_row(
        "SELECT state FROM staging WHERE attempt='crashed-B'",
        [],
        |r| r.get(0),
    )?;
    assert_eq!(pending, "pending");
    spike::recover_confirmed_dead(&mut reopened, "crashed-B")?;
    let abandoned: String = reopened.query_row(
        "SELECT state FROM staging WHERE attempt='crashed-B'",
        [],
        |r| r.get(0),
    )?;
    assert_eq!(abandoned, "abandoned");
    integrity(&reopened)?;
    spike::publish(&mut reopened, "B", &[spike::document_b()])?;
    assert_eq!(Reader::begin(&path)?.generation(), "B");
    assert!(spike::recover_confirmed_dead(&mut reopened, "crashed-B").is_err());
    Ok(())
}

#[test]
fn backup_rebuild_preserve_human_files_and_readers_and_refuse_overwrite() -> Result<()> {
    let dir = Temporary::new();
    let path = dir.db();
    let config = dir.0.join("config.toml");
    let notes = dir.0.join("human-notes.md");
    fs::write(&config, b"user configuration").unwrap();
    fs::write(&notes, b"irreplaceable human notes").unwrap();
    let mut writer = spike::initialize(&path)?;
    spike::publish(&mut writer, "A", &[spike::document_a()])?;
    let old = Reader::begin(&path)?;
    spike::publish(&mut writer, "B", &[spike::document_b()])?;
    let backup = dir.0.join("backup.sqlite");
    spike::backup(&writer, &backup)?;
    assert_eq!(Reader::begin(&backup)?.generation(), "B");
    integrity(&spike::open_existing(&backup)?)?;
    let bytes = fs::read(&backup)?;
    assert!(spike::backup(&writer, &backup).is_err());
    assert_eq!(fs::read(&backup)?, bytes);
    assert!(spike::backup(&writer, &notes).is_err());
    assert!(spike::initialize(&config).is_err());
    let foreign = dir.0.join("foreign.sqlite");
    let foreign_connection = rusqlite::Connection::open(&foreign)?;
    foreign_connection.execute_batch("PRAGMA user_version=999; CREATE TABLE human_notes(note TEXT); INSERT INTO human_notes VALUES('keep me');")?;
    drop(foreign_connection);
    let foreign_bytes = fs::read(&foreign)?;
    assert!(spike::backup(&writer, &foreign).is_err());
    assert_eq!(fs::read(&foreign)?, foreign_bytes);
    assert!(spike::open_existing(&foreign).is_err());
    spike::rebuild(&mut writer, "rebuilt", &[spike::document_b()])?;
    assert_eq!(old.facts()?[0].bytes, spike::document_a().bytes);
    assert_eq!(old.search("OldWidget", false)?, ["src/old_widget.rs"]);
    assert_eq!(Reader::begin(&path)?.generation(), "rebuilt");
    assert!(Reader::begin(&path)?.search("OldWidget", false)?.is_empty());
    assert_eq!(fs::read(config)?, b"user configuration");
    assert_eq!(fs::read(notes)?, b"irreplaceable human notes");
    integrity(&writer)?;
    Ok(())
}

#[test]
fn future_schema_and_foreign_application_are_refused_without_recreation() -> Result<()> {
    for change in ["PRAGMA user_version=999", "PRAGMA application_id=12345"] {
        let dir = Temporary::new();
        let path = dir.db();
        let mut writer = spike::initialize(&path)?;
        spike::publish(&mut writer, "A", &[spike::document_a()])?;
        writer.execute_batch(change)?;
        assert!(
            spike::rebuild(&mut writer, "replacement", &[spike::document_b()])
                .unwrap_err()
                .to_string()
                .contains("unsupported spike schema")
        );
        let backup = dir.0.join("denied-backup.sqlite");
        assert!(
            spike::backup(&writer, &backup)
                .unwrap_err()
                .to_string()
                .contains("unsupported spike schema")
        );
        assert!(!backup.exists());
        writer.execute_batch("PRAGMA wal_checkpoint(TRUNCATE)")?;
        drop(writer);
        let original = fs::read(&path)?;
        let error = spike::open_existing(&path).unwrap_err();
        assert!(error.to_string().contains("unsupported spike schema"));
        assert_eq!(fs::read(&path)?, original);
        assert!(spike::initialize(&path).is_err());
        assert_eq!(fs::read(&path)?, original);
    }
    let dir = Temporary::new();
    assert!(spike::open_existing(&dir.db()).is_err());
    assert!(!dir.db().exists());
    Ok(())
}

#[test]
fn source_foreign_keys_hashes_and_invalid_spans_are_enforced() -> Result<()> {
    let dir = Temporary::new();
    let path = dir.db();
    let mut writer = spike::initialize(&path)?;
    spike::publish(&mut writer, "A", &[spike::document_a()])?;
    let orphan=writer.execute("INSERT INTO facts(generation,path,hash,name,start_byte,end_byte) VALUES('A','absent.rs','absent','bad',0,1)",[]).unwrap_err();
    assert!(
        matches!(orphan,rusqlite::Error::SqliteFailure(error,_) if error.code==ErrorCode::ConstraintViolation)
    );
    let doc = spike::Document {
        end_byte: usize::MAX,
        ..spike::document_b()
    };
    assert!(spike::publish(&mut writer, "bad", &[doc]).is_err());
    assert_eq!(Reader::begin(&path)?.generation(), "A");
    assert_eq!(
        writer.query_row("SELECT count(*) FROM generations", [], |r| r
            .get::<_, i64>(0))?,
        1
    );
    // Same source in a new generation deduplicates the retained immutable blob.
    spike::publish(&mut writer, "same", &[spike::document_a()])?;
    assert_eq!(
        writer.query_row("SELECT count(*) FROM blobs", [], |r| r.get::<_, i64>(0))?,
        1
    );
    let hash = blake3::hash(spike::document_a().bytes).to_hex().to_string();
    let referenced = writer
        .execute("DELETE FROM blobs WHERE hash=?1", params![hash])
        .unwrap_err();
    assert!(
        matches!(referenced,rusqlite::Error::SqliteFailure(error,_) if error.code==ErrorCode::ConstraintViolation)
    );
    writer.execute("UPDATE blobs SET bytes=X'00' WHERE hash=?1", params![hash])?;
    assert!(
        Reader::begin(&path)?
            .facts()
            .unwrap_err()
            .to_string()
            .contains("corrupt source")
    );
    Ok(())
}

#[test]
fn bundled_sqlite_fts5_and_trigram_are_available_without_load_extension() -> Result<()> {
    let dir = Temporary::new();
    let path = dir.db();
    let mut writer = spike::initialize(&path)?;
    let fts5: bool =
        writer.query_row("SELECT sqlite_compileoption_used('ENABLE_FTS5')", [], |r| {
            r.get(0)
        })?;
    assert!(fts5);
    spike::publish(&mut writer, "A", &[spike::document_a()])?;
    assert_eq!(
        Reader::begin(&path)?.search("name:Widget", true)?,
        ["src/old_widget.rs"]
    );
    assert_eq!(
        Reader::begin(&path)?.search("path:old", false)?,
        ["src/old_widget.rs"]
    );
    assert_eq!(
        Reader::begin(&path)?.search("café", false)?,
        ["src/old_widget.rs"]
    );
    Ok(())
}
