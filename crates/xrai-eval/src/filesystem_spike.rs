//! M0-08 development experiment. Unix native bytes are the identity input.
//!
//! Symlinks are never followed. This is an inventory spike, not a security
//! sandbox: a concurrent rename of an ancestor directory is outside its model.
use std::io::Read;
use std::os::unix::{
    ffi::OsStrExt,
    fs::{MetadataExt, OpenOptionsExt},
};
use std::{
    fs, io,
    path::{Component, Path, PathBuf},
};

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Reason {
    InternalState,
    ConfigExcluded,
    Symlink,
    NonRegular,
    Removed,
    PermissionDenied,
    ReadFailed,
    ChangedDuringRead,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Diagnostic {
    pub path: Vec<u8>,
    pub reason: Reason,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Source {
    pub path: Vec<u8>,
    pub bytes: Vec<u8>,
    pub hash: String,
}
#[derive(Debug)]
pub struct Inventory {
    pub checkout_id: String,
    pub sources: Vec<Source>,
    pub diagnostics: Vec<Diagnostic>,
}
#[derive(Clone, Debug, Default)]
pub struct Config {
    pub excluded_subtrees: Vec<PathBuf>,
}

impl Config {
    /// Only explicit relative subtree paths are accepted; no glob semantics.
    pub fn validate(&self) -> io::Result<()> {
        for path in &self.excluded_subtrees {
            if path.as_os_str().is_empty()
                || path
                    .components()
                    .any(|c| !matches!(c, Component::Normal(_)))
            {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidInput,
                    "exclusions must be nonempty relative subtree paths",
                ));
            }
        }
        Ok(())
    }
    fn exclusion(&self, path: &Path) -> Option<Reason> {
        if path.components().any(
            |part| matches!(part, Component::Normal(name) if name == ".git" || name == ".xrai"),
        ) {
            return Some(Reason::InternalState);
        }
        if self
            .excluded_subtrees
            .iter()
            .any(|excluded| path.starts_with(excluded))
        {
            return Some(Reason::ConfigExcluded);
        }
        None
    }
}

fn native(path: &Path) -> Vec<u8> {
    path.as_os_str().as_bytes().to_vec()
}
fn failure(error: &io::Error) -> Reason {
    match error.kind() {
        io::ErrorKind::NotFound => Reason::Removed,
        io::ErrorKind::PermissionDenied => Reason::PermissionDenied,
        _ => Reason::ReadFailed,
    }
}

/// Identity includes the canonical root and its native filesystem identity.
/// Git metadata and display strings are advisory, never keys.
pub fn checkout_id(root: &Path) -> io::Result<String> {
    let root = root.canonicalize()?;
    let metadata = fs::metadata(&root)?;
    if !metadata.is_dir() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "checkout root must be a directory",
        ));
    }
    let mut hash = blake3::Hasher::new();
    hash.update(b"xrai-filesystem-spike-checkout-v1\0");
    let bytes = native(&root);
    hash.update(&(bytes.len() as u64).to_le_bytes());
    hash.update(&bytes);
    hash.update(&metadata.dev().to_le_bytes());
    hash.update(&metadata.ino().to_le_bytes());
    Ok(hash.finalize().to_hex().to_string())
}

/// State destinations are disjoint even for equal checkout names/content.
pub fn state_directory(cache_root: &Path, root: &Path) -> io::Result<PathBuf> {
    Ok(cache_root.join(checkout_id(root)?))
}

/// Final component is opened with O_NOFOLLOW on both mandatory Unix hosts.
#[cfg(target_os = "linux")]
const NOFOLLOW: i32 = 0x20000;
#[cfg(target_os = "macos")]
const NOFOLLOW: i32 = 0x100;

/// Capture source bytes, rejecting links in every checked path component.
/// This also provides typed errors when discovery and reading are separated.
pub fn capture(root: &Path, relative: &Path) -> Result<Source, Diagnostic> {
    capture_after_open(root, relative, || {})
}

/// Deterministic race probe hook; the observer runs after opening the source.
/// This development-only entry point can remove/replace a discovered path.
pub fn capture_after_open(
    root: &Path,
    relative: &Path,
    observer: impl FnOnce(),
) -> Result<Source, Diagnostic> {
    let diagnostic = |reason| Diagnostic {
        path: native(relative),
        reason,
    };
    if relative.as_os_str().is_empty()
        || relative
            .components()
            .any(|c| !matches!(c, Component::Normal(_)))
    {
        return Err(diagnostic(Reason::ReadFailed));
    }
    let mut path = root.to_path_buf();
    for component in relative.components() {
        path.push(component.as_os_str());
        let metadata = fs::symlink_metadata(&path).map_err(|e| diagnostic(failure(&e)))?;
        if metadata.file_type().is_symlink() {
            return Err(diagnostic(Reason::Symlink));
        }
    }
    let before = fs::symlink_metadata(&path).map_err(|e| diagnostic(failure(&e)))?;
    if !before.is_file() {
        return Err(diagnostic(Reason::NonRegular));
    }
    let mut file = fs::OpenOptions::new()
        .read(true)
        .custom_flags(NOFOLLOW)
        .open(&path)
        .map_err(|e| diagnostic(failure(&e)))?;
    let opened = file.metadata().map_err(|e| diagnostic(failure(&e)))?;
    if (before.dev(), before.ino()) != (opened.dev(), opened.ino()) {
        return Err(diagnostic(Reason::ChangedDuringRead));
    }
    observer();
    let mut bytes = Vec::new();
    file.read_to_end(&mut bytes)
        .map_err(|e| diagnostic(failure(&e)))?;
    let after = file.metadata().map_err(|e| diagnostic(failure(&e)))?;
    if (opened.len(), opened.modified().ok()) != (after.len(), after.modified().ok())
        || after.len() != bytes.len() as u64
    {
        return Err(diagnostic(Reason::ChangedDuringRead));
    }
    let named = fs::symlink_metadata(&path).map_err(|e| diagnostic(failure(&e)))?;
    if named.file_type().is_symlink() || (named.dev(), named.ino()) != (after.dev(), after.ino()) {
        return Err(diagnostic(Reason::ChangedDuringRead));
    }
    Ok(Source {
        path: native(relative),
        hash: blake3::hash(&bytes).to_hex().to_string(),
        bytes,
    })
}

pub fn inventory(root: &Path, config: &Config) -> io::Result<Inventory> {
    config.validate()?;
    let root = root.canonicalize()?;
    let mut result = Inventory {
        checkout_id: checkout_id(&root)?,
        sources: Vec::new(),
        diagnostics: Vec::new(),
    };
    walk(&root, Path::new(""), config, &mut result);
    result.sources.sort_by(|a, b| a.path.cmp(&b.path));
    result.diagnostics.sort_by(|a, b| a.path.cmp(&b.path));
    Ok(result)
}

fn walk(root: &Path, relative: &Path, config: &Config, result: &mut Inventory) {
    let entries = match fs::read_dir(root.join(relative)) {
        Ok(entries) => entries,
        Err(error) => {
            result.diagnostics.push(Diagnostic {
                path: native(relative),
                reason: failure(&error),
            });
            return;
        }
    };
    for entry in entries {
        let entry = match entry {
            Ok(entry) => entry,
            Err(error) => {
                result.diagnostics.push(Diagnostic {
                    path: native(relative),
                    reason: failure(&error),
                });
                continue;
            }
        };
        let path = relative.join(entry.file_name());
        let reason = config.exclusion(&path);
        if let Some(reason) = reason {
            result.diagnostics.push(Diagnostic {
                path: native(&path),
                reason,
            });
            continue;
        }
        let metadata = match fs::symlink_metadata(entry.path()) {
            Ok(metadata) => metadata,
            Err(error) => {
                result.diagnostics.push(Diagnostic {
                    path: native(&path),
                    reason: failure(&error),
                });
                continue;
            }
        };
        if metadata.file_type().is_symlink() {
            result.diagnostics.push(Diagnostic {
                path: native(&path),
                reason: Reason::Symlink,
            });
        } else if metadata.is_dir() {
            walk(root, &path, config, result);
        } else {
            match capture(root, &path) {
                Ok(source) => result.sources.push(source),
                Err(diagnostic) => result.diagnostics.push(diagnostic),
            }
        }
    }
}

/// Read .gitfile as opaque bytes to identify an advisory worktree pointer.
/// The referenced path is deliberately never opened or used for state keys.
pub fn gitfile_pointer(root: &Path) -> io::Result<Option<Vec<u8>>> {
    let path = root.join(".git");
    match fs::symlink_metadata(&path) {
        Ok(metadata) if metadata.is_file() => {
            let source = capture(root, Path::new(".git"))
                .map_err(|d| io::Error::other(format!("gitfile: {:?}", d.reason)))?;
            let prefix = b"gitdir: ";
            if !source.bytes.starts_with(prefix) {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "invalid .gitfile",
                ));
            }
            let pointer = source.bytes[prefix.len()..]
                .strip_suffix(b"\n")
                .unwrap_or(&source.bytes[prefix.len()..]);
            let pointer = pointer.strip_suffix(b"\r").unwrap_or(pointer);
            if pointer.is_empty() || pointer.contains(&b'\n') || pointer.contains(&b'\r') {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "invalid .gitfile pointer",
                ));
            }
            Ok(Some(pointer.to_vec()))
        }
        Ok(_) => Ok(None),
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(None),
        Err(error) => Err(error),
    }
}
