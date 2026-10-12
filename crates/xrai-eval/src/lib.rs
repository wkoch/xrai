//! Development evaluation boundary for xrai.
//!
//! The local harness lives in `harness/`. The SQLite experiment belongs to M0-07;
//! it is not a production storage API. The installed `xrai` binary does not
//! depend on this crate.

pub mod context_spike;
pub mod filesystem_spike;
pub mod parsing_spike;
pub mod semantics_spike;
pub mod sqlite_spike;
pub mod worker_persistent;
pub mod worker_spike;
