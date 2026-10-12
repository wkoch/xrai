//! Disposable M0-07 experiment: immutable source generations in bundled SQLite.
//!
//! This module deliberately has no parser, domain API, migration or retention
//! policy. Historical generations are retained, including their FTS documents.
//! Recovery is explicit: a pending attempt is not assumed dead just because a
//! reader sees it. Only the process supervisor can confirm termination.

use rusqlite::{Connection, OpenFlags, Transaction, TransactionBehavior, params};
use std::{error::Error, fs::OpenOptions, io, path::Path, time::Duration};

pub type Result<T> = std::result::Result<T, Box<dyn Error + Send + Sync>>;
pub const WRITER_WAIT: Duration = Duration::from_millis(150);
const APPLICATION_ID: i64 = 0x58525350; // XRSP: distinct from a future production DB.
const SCHEMA_VERSION: i64 = 1;

const SCHEMA: &str = r#"
CREATE TABLE generations(id TEXT PRIMARY KEY NOT NULL);
CREATE TABLE blobs(hash TEXT PRIMARY KEY NOT NULL, bytes BLOB NOT NULL);
CREATE TABLE sources(
    generation TEXT NOT NULL REFERENCES generations(id),
    path TEXT NOT NULL,
    hash TEXT NOT NULL REFERENCES blobs(hash),
    PRIMARY KEY(generation,path), UNIQUE(generation,path,hash)
);
CREATE TABLE facts(
    id INTEGER PRIMARY KEY,
    generation TEXT NOT NULL,
    path TEXT NOT NULL,
    hash TEXT NOT NULL,
    name TEXT NOT NULL,
    start_byte INTEGER NOT NULL CHECK(start_byte >= 0),
    end_byte INTEGER NOT NULL CHECK(end_byte > start_byte),
    FOREIGN KEY(generation,path,hash) REFERENCES sources(generation,path,hash)
);
CREATE TABLE publication(
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    generation TEXT REFERENCES generations(id)
);
INSERT INTO publication VALUES(1,NULL);
CREATE TABLE staging(
    attempt TEXT PRIMARY KEY NOT NULL,
    generation TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('pending','abandoned'))
);
CREATE VIRTUAL TABLE documents USING fts5(
    generation UNINDEXED, path, name, source, tokenize='unicode61'
);
CREATE VIRTUAL TABLE substrings USING fts5(
    generation UNINDEXED, path, name, tokenize='trigram'
);
"#;

fn invalid(message: impl Into<String>) -> Box<dyn Error + Send + Sync> {
    io::Error::new(io::ErrorKind::InvalidData, message.into()).into()
}

fn validate_schema(connection: &Connection) -> Result<()> {
    let application: i64 = connection.pragma_query_value(None, "application_id", |r| r.get(0))?;
    let version: i64 = connection.pragma_query_value(None, "user_version", |r| r.get(0))?;
    if application != APPLICATION_ID || version != SCHEMA_VERSION {
        return Err(invalid(format!(
            "unsupported spike schema: application_id={application}, user_version={version}; database preserved"
        )));
    }
    Ok(())
}

/// Explicit initialization only; never overwrites an existing file.
pub fn initialize(path: &Path) -> Result<Connection> {
    OpenOptions::new().write(true).create_new(true).open(path)?;
    let mut connection = Connection::open_with_flags(path, OpenFlags::SQLITE_OPEN_READ_WRITE)?;
    connection.busy_timeout(WRITER_WAIT)?;
    connection.pragma_update(None, "journal_mode", "WAL")?;
    connection.pragma_update(None, "synchronous", "FULL")?;
    connection.pragma_update(None, "foreign_keys", true)?;
    let transaction = connection.transaction_with_behavior(TransactionBehavior::Immediate)?;
    transaction.execute_batch(SCHEMA)?;
    transaction.pragma_update(None, "application_id", APPLICATION_ID)?;
    transaction.pragma_update(None, "user_version", SCHEMA_VERSION)?;
    transaction.commit()?;
    Ok(connection)
}

/// No CREATE flag, no automatic migration or cache deletion.
pub fn open_existing(path: &Path) -> Result<Connection> {
    let connection = Connection::open_with_flags(path, OpenFlags::SQLITE_OPEN_READ_WRITE)?;
    validate_schema(&connection)?;
    connection.busy_timeout(WRITER_WAIT)?;
    connection.pragma_update(None, "foreign_keys", true)?;
    connection.pragma_update(None, "synchronous", "FULL")?;
    Ok(connection)
}

/// Fixture facts are manually supplied; extraction is outside this experiment.
#[derive(Clone, Debug)]
pub struct Document<'a> {
    pub path: &'a str,
    pub name: &'a str,
    pub bytes: &'a [u8],
    pub start_byte: usize,
    pub end_byte: usize,
}

fn insert_generation(
    transaction: &Transaction<'_>,
    generation: &str,
    docs: &[Document<'_>],
) -> Result<()> {
    transaction.execute("INSERT INTO generations VALUES(?1)", [generation])?;
    for doc in docs {
        let text = std::str::from_utf8(doc.bytes)?;
        if doc.start_byte >= doc.end_byte
            || doc.end_byte > doc.bytes.len()
            || !text.is_char_boundary(doc.start_byte)
            || !text.is_char_boundary(doc.end_byte)
        {
            return Err(invalid("invalid source byte span"));
        }
        let hash = blake3::hash(doc.bytes).to_hex().to_string();
        transaction.execute(
            "INSERT OR IGNORE INTO blobs VALUES(?1,?2)",
            params![hash, doc.bytes],
        )?;
        let stored: Vec<u8> =
            transaction.query_row("SELECT bytes FROM blobs WHERE hash=?1", [&hash], |r| {
                r.get(0)
            })?;
        if stored != doc.bytes {
            return Err(invalid("source hash collision or corrupted blob"));
        }
        transaction.execute(
            "INSERT INTO sources VALUES(?1,?2,?3)",
            params![generation, doc.path, hash],
        )?;
        transaction.execute("INSERT INTO facts(generation,path,hash,name,start_byte,end_byte) VALUES(?1,?2,?3,?4,?5,?6)", params![generation,doc.path,hash,doc.name,doc.start_byte as i64,doc.end_byte as i64])?;
        transaction.execute(
            "INSERT INTO documents(generation,path,name,source) VALUES(?1,?2,?3,?4)",
            params![generation, doc.path, doc.name, text],
        )?;
        transaction.execute(
            "INSERT INTO substrings(generation,path,name) VALUES(?1,?2,?3)",
            params![generation, doc.path, doc.name],
        )?;
    }
    transaction.execute(
        "UPDATE publication SET generation=?1 WHERE singleton=1",
        [generation],
    )?;
    Ok(())
}

pub fn publish(connection: &mut Connection, generation: &str, docs: &[Document<'_>]) -> Result<()> {
    let transaction = connection.transaction_with_behavior(TransactionBehavior::Immediate)?;
    insert_generation(&transaction, generation, docs)?;
    transaction.commit()?;
    Ok(())
}

/// Persist the intent independently, so interruption leaves a diagnosable row.
/// An intent is not a publication and not proof that its worker has died.
pub fn record_attempt(connection: &mut Connection, attempt: &str, generation: &str) -> Result<()> {
    let transaction = connection.transaction_with_behavior(TransactionBehavior::Immediate)?;
    transaction.execute(
        "INSERT INTO staging VALUES(?1,?2,'pending')",
        params![attempt, generation],
    )?;
    transaction.commit()?;
    Ok(())
}

/// Test supervisor must have killed AND waited for the process before calling.
pub fn recover_confirmed_dead(connection: &mut Connection, attempt: &str) -> Result<()> {
    let transaction = connection.transaction_with_behavior(TransactionBehavior::Immediate)?;
    let generation: String = transaction.query_row(
        "SELECT generation FROM staging WHERE attempt=?1 AND state='pending'",
        [attempt],
        |r| r.get(0),
    )?;
    let published: bool = transaction.query_row(
        "SELECT EXISTS(SELECT 1 FROM generations WHERE id=?1)",
        [&generation],
        |r| r.get(0),
    )?;
    if published {
        return Err(invalid("attempt already committed; cannot label abandoned"));
    }
    transaction.execute(
        "UPDATE staging SET state='abandoned' WHERE attempt=?1",
        [attempt],
    )?;
    transaction.commit()?;
    Ok(())
}

/// Deliberate pre-commit process fixture. Ready is signaled AFTER writes exist in
/// the transaction; parent terminates it. Never exposed by the product binary.
pub fn hold_uncommitted(path: &Path, ready: &Path) -> Result<()> {
    let mut connection = open_existing(path)?;
    record_attempt(&mut connection, "crashed-B", "B")?;
    let transaction = connection.transaction_with_behavior(TransactionBehavior::Immediate)?;
    insert_generation(&transaction, "B", &[document_b()])?;
    transaction.execute("DELETE FROM staging WHERE attempt='crashed-B'", [])?;
    std::fs::write(ready, b"uncommitted B; writer lock held")?;
    // Bound the fixture lifetime even if the parent disappears.
    std::thread::sleep(Duration::from_secs(30));
    drop(transaction); // Rollback, never a delayed commit.
    Ok(())
}

#[derive(Debug, PartialEq, Eq)]
pub struct ReadFact {
    pub generation: String,
    pub path: String,
    pub hash: String,
    pub name: String,
    pub bytes: Vec<u8>,
    pub start_byte: usize,
    pub end_byte: usize,
}

pub struct Reader {
    connection: Connection,
    generation: String,
}

impl Reader {
    pub fn generation(&self) -> &str {
        &self.generation
    }

    /// Begin and establish the SQLite read snapshot before returning.
    pub fn begin(path: &Path) -> Result<Self> {
        let connection = open_existing(path)?;
        connection.execute_batch("BEGIN DEFERRED")?;
        let generation: Option<String> = connection.query_row(
            "SELECT generation FROM publication WHERE singleton=1",
            [],
            |r| r.get(0),
        )?;
        Ok(Self {
            connection,
            generation: generation.ok_or_else(|| invalid("no published generation"))?,
        })
    }

    pub fn facts(&self) -> Result<Vec<ReadFact>> {
        let mut statement = self.connection.prepare("SELECT f.generation,f.path,f.hash,f.name,b.bytes,f.start_byte,f.end_byte FROM facts f JOIN sources s USING(generation,path,hash) JOIN blobs b USING(hash) WHERE f.generation=?1 ORDER BY f.path")?;
        let rows = statement.query_map([&self.generation], |r| {
            Ok(ReadFact {
                generation: r.get(0)?,
                path: r.get(1)?,
                hash: r.get(2)?,
                name: r.get(3)?,
                bytes: r.get(4)?,
                start_byte: r.get::<_, i64>(5)? as usize,
                end_byte: r.get::<_, i64>(6)? as usize,
            })
        })?;
        let facts = rows.collect::<rusqlite::Result<Vec<_>>>()?;
        for fact in &facts {
            let text = std::str::from_utf8(&fact.bytes)?;
            if blake3::hash(&fact.bytes).to_hex().as_str() != fact.hash
                || fact.start_byte >= fact.end_byte
                || fact.end_byte > fact.bytes.len()
                || !text.is_char_boundary(fact.start_byte)
                || !text.is_char_boundary(fact.end_byte)
            {
                return Err(invalid("corrupt source hash or span"));
            }
        }
        Ok(facts)
    }

    /// Exact FTS expression, revision-bound. Trigram supports substrings >=3 chars.
    pub fn search(&self, expression: &str, substring: bool) -> Result<Vec<String>> {
        let sql = if substring {
            "SELECT path FROM substrings WHERE substrings MATCH ?1 AND generation=?2 ORDER BY path"
        } else {
            "SELECT path FROM documents WHERE documents MATCH ?1 AND generation=?2 ORDER BY path"
        };
        let mut statement = self.connection.prepare(sql)?;
        let rows = statement.query_map(params![expression, self.generation], |r| r.get(0))?;
        Ok(rows.collect::<rusqlite::Result<Vec<_>>>()?)
    }
}

/// SQLite's online backup includes committed WAL state. The destination must be
/// new, and the API never recursively removes or copies a project directory.
pub fn backup(connection: &Connection, destination: &Path) -> Result<()> {
    validate_schema(connection)?;
    OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(destination)?;
    let mut output = Connection::open_with_flags(destination, OpenFlags::SQLITE_OPEN_READ_WRITE)?;
    let backup = rusqlite::backup::Backup::new(connection, &mut output)?;
    backup.run_to_completion(16, Duration::from_millis(5), None)?;
    drop(backup);
    validate_schema(&output)?;
    Ok(())
}

/// Rebuild derived tables transactionally in this ONE recognized database.
/// No filesystem deletion. Readers with older SQLite snapshots remain stable.
pub fn rebuild(connection: &mut Connection, generation: &str, docs: &[Document<'_>]) -> Result<()> {
    validate_schema(connection)?;
    let transaction = connection.transaction_with_behavior(TransactionBehavior::Immediate)?;
    transaction.execute_batch("UPDATE publication SET generation=NULL; DELETE FROM documents; DELETE FROM substrings; DELETE FROM facts; DELETE FROM sources; DELETE FROM generations; DELETE FROM blobs; DELETE FROM staging;")?;
    insert_generation(&transaction, generation, docs)?;
    transaction.commit()?;
    Ok(())
}

pub fn document_a() -> Document<'static> {
    let bytes = "pub fn OldWidget() { /* café 🌱 */ }\r\n".as_bytes();
    Document {
        path: "src/old_widget.rs",
        name: "OldWidget",
        bytes,
        start_byte: 0,
        end_byte: bytes.len(),
    }
}

pub fn document_b() -> Document<'static> {
    let bytes = "pub fn NewWidget() { /* revisão B */ }\r\n".as_bytes();
    Document {
        path: "src/new_widget.rs",
        name: "NewWidget",
        bytes,
        start_byte: 0,
        end_byte: bytes.len(),
    }
}
