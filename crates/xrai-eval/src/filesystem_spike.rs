//! M0-08 development experiment. Unix native bytes are the identity input.
//!
//! Handle-anchored capture, ADR 023. Hashes identify delivered immutable bytes;
//! revalidated live bindings are observations, never atomic filesystem snapshots.
use std::io::Read;
use std::os::unix::{ffi::OsStrExt, fs::MetadataExt};
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
    LimitExceeded,
    MountBoundary,
    UnsupportedResolution,
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
            if !valid_relative(path) {
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
    Ok(checkout_identity(&root, &metadata))
}
fn checkout_identity(root: &Path, metadata: &fs::Metadata) -> String {
    let mut hash = blake3::Hasher::new();
    hash.update(b"xrai-filesystem-spike-checkout-v1\0");
    let bytes = native(root);
    hash.update(&(bytes.len() as u64).to_le_bytes());
    hash.update(&bytes);
    hash.update(&metadata.dev().to_le_bytes());
    hash.update(&metadata.ino().to_le_bytes());
    hash.finalize().to_hex().to_string()
}

/// State destinations are disjoint even for equal checkout names/content.
pub fn state_directory(cache_root: &Path, root: &Path) -> io::Result<PathBuf> {
    Ok(cache_root.join(checkout_id(root)?))
}

/// Frozen experimental ceiling; enforced during reading, not only from metadata.
pub const DEFAULT_READ_LIMIT: usize = 8 * 1024 * 1024;

/// Development-only deterministic observation points. No sleeps are required.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ProbePoint {
    RootAdmitted,
    AncestorOpened,
    SourceOpened,
    ChunkRead,
    DirectoryOpened,
    BeforePublish,
}

type Identity = (u64, u64);
type Stamp = (u64, Option<std::time::SystemTime>, i64, i64);
type Bindings = Vec<(PathBuf, Identity, Option<Stamp>)>;
fn stamp(metadata: &fs::Metadata) -> Stamp {
    (
        metadata.len(),
        metadata.modified().ok(),
        metadata.ctime(),
        metadata.ctime_nsec(),
    )
}
fn identity(metadata: &fs::Metadata) -> Identity {
    (metadata.dev(), metadata.ino())
}
fn diagnostic(path: &Path, reason: Reason) -> Diagnostic {
    Diagnostic {
        path: native(path),
        reason,
    }
}
fn valid_relative(path: &Path) -> bool {
    let bytes = path.as_os_str().as_bytes();
    !bytes.is_empty()
        && !bytes.contains(&0)
        && bytes
            .split(|b| *b == b'/')
            .all(|part| !part.is_empty() && part != b"." && part != b"..")
}
fn resolution_error(error: rustix::io::Errno) -> Reason {
    use rustix::io::Errno;
    match error {
        Errno::LOOP => Reason::Symlink,
        Errno::XDEV => Reason::MountBoundary,
        Errno::NOSYS => Reason::UnsupportedResolution,
        Errno::AGAIN | Errno::NOTDIR => Reason::ChangedDuringRead,
        _ => failure(&io::Error::from(error)),
    }
}

struct Root {
    locator: PathBuf,
    file: fs::File,
    identity: Identity,
    lineage: Vec<Identity>,
}
// Absolute root admission/revalidation also walks handles: replacing a parent
// of the checkout with a link must not preserve a misleading locator binding.
fn absolute_directory(locator: &Path) -> Result<(fs::File, Vec<Identity>), rustix::io::Errno> {
    use rustix::fs::{Mode, OFlags};
    let flags = OFlags::RDONLY | OFlags::DIRECTORY | OFlags::NOFOLLOW | OFlags::CLOEXEC;
    let mut file = fs::File::from(rustix::fs::open("/", flags, Mode::empty())?);
    let mut lineage = vec![identity(
        &file.metadata().map_err(|_| rustix::io::Errno::IO)?,
    )];
    for component in locator.components() {
        if let Component::Normal(name) = component {
            file = fs::File::from(rustix::fs::openat(&file, name, flags, Mode::empty())?);
            lineage.push(identity(
                &file.metadata().map_err(|_| rustix::io::Errno::IO)?,
            ));
        }
    }
    Ok((file, lineage))
}
impl Root {
    fn admit(path: &Path) -> io::Result<Self> {
        // Explicit root selection may resolve aliases at admission only.
        let locator = path.canonicalize()?;
        let (file, lineage) = absolute_directory(&locator)?;
        let identity = identity(&file.metadata()?);
        Ok(Self {
            locator,
            file,
            identity,
            lineage,
        })
    }
    fn root_valid(&self) -> Result<(), Reason> {
        let (_, lineage) = absolute_directory(&self.locator).map_err(resolution_error)?;
        if lineage != self.lineage {
            return Err(Reason::ChangedDuringRead);
        }
        Ok(())
    }
    fn open_child(
        &self,
        directory: &fs::File,
        name: &Path,
        is_dir: bool,
    ) -> Result<fs::File, Reason> {
        use rustix::fs::{Mode, OFlags};
        let mut flags = OFlags::RDONLY | OFlags::NOFOLLOW | OFlags::CLOEXEC | OFlags::NONBLOCK;
        if is_dir {
            flags |= OFlags::DIRECTORY;
        }
        #[cfg(target_os = "linux")]
        let fd = rustix::fs::openat2(
            directory,
            name,
            flags,
            Mode::empty(),
            rustix::fs::ResolveFlags::BENEATH
                | rustix::fs::ResolveFlags::NO_SYMLINKS
                | rustix::fs::ResolveFlags::NO_XDEV,
        )
        .map_err(resolution_error)?;
        #[cfg(target_os = "macos")]
        let fd =
            rustix::fs::openat(directory, name, flags, Mode::empty()).map_err(resolution_error)?;
        let file = fs::File::from(fd);
        if file.metadata().map_err(|e| failure(&e))?.dev() != self.identity.0 {
            return Err(Reason::MountBoundary);
        }
        Ok(file)
    }
    fn open(
        &self,
        relative: &Path,
        is_dir: bool,
        observer: &mut impl FnMut(ProbePoint, &Path),
    ) -> Result<(fs::File, Bindings), Reason> {
        if !valid_relative(relative) {
            return Err(Reason::ReadFailed);
        }
        let mut parent = self.file.try_clone().map_err(|e| failure(&e))?;
        let components: Vec<_> = relative.components().collect();
        let mut path = PathBuf::new();
        let mut bindings = Vec::new();
        for (index, part) in components.iter().enumerate() {
            let name = Path::new(part.as_os_str());
            path.push(name);
            let final_part = index + 1 == components.len();
            // Typed static diagnoses without following symlinks; nonblocking
            // open and descriptor type validation also cover replacement races.
            let stat = rustix::fs::statat(&parent, name, rustix::fs::AtFlags::SYMLINK_NOFOLLOW)
                .map_err(resolution_error)?;
            let kind = rustix::fs::FileType::from_raw_mode(stat.st_mode);
            if kind == rustix::fs::FileType::Symlink {
                return Err(Reason::Symlink);
            }
            if final_part && !is_dir && kind != rustix::fs::FileType::RegularFile {
                return Err(Reason::NonRegular);
            }
            let next = self.open_child(&parent, name, !final_part || is_dir)?;
            let metadata = next.metadata().map_err(|e| failure(&e))?;
            if (!final_part || is_dir) && !metadata.is_dir() {
                return Err(Reason::NonRegular);
            }
            if final_part && !is_dir && !metadata.is_file() {
                return Err(Reason::NonRegular);
            }
            bindings.push((
                path.clone(),
                identity(&metadata),
                (final_part && !is_dir).then(|| stamp(&metadata)),
            ));
            if !final_part {
                observer(ProbePoint::AncestorOpened, &path);
            }
            parent = next;
        }
        Ok((parent, bindings))
    }
    fn reconcile(&self, bindings: &Bindings) -> Result<(), Reason> {
        self.root_valid()?;
        for (index, (path, expected, revision)) in bindings.iter().enumerate() {
            let directory = index + 1 != bindings.len();
            let (file, _) = self.open(path, directory, &mut |_, _| {})?;
            let metadata = file.metadata().map_err(|e| failure(&e))?;
            if identity(&metadata) != *expected || revision.is_some_and(|s| s != stamp(&metadata)) {
                return Err(Reason::ChangedDuringRead);
            }
        }
        Ok(())
    }
    fn capture(
        &self,
        relative: &Path,
        limit: usize,
        observer: &mut impl FnMut(ProbePoint, &Path),
    ) -> Result<(Source, Bindings), Diagnostic> {
        let bad = |reason| diagnostic(relative, reason);
        let (mut file, bindings) = self.open(relative, false, observer).map_err(bad)?;
        let opened = file.metadata().map_err(|e| bad(failure(&e)))?;
        if opened.len() > limit as u64 {
            return Err(bad(Reason::LimitExceeded));
        }
        observer(ProbePoint::SourceOpened, relative);
        let mut bytes = Vec::new();
        let mut chunk = [0u8; 8192];
        loop {
            let count = file.read(&mut chunk).map_err(|e| bad(failure(&e)))?;
            if count == 0 {
                break;
            }
            if count > limit.saturating_sub(bytes.len()) {
                return Err(bad(Reason::LimitExceeded));
            }
            bytes.extend_from_slice(&chunk[..count]);
            observer(ProbePoint::ChunkRead, relative);
        }
        let after = file.metadata().map_err(|e| bad(failure(&e)))?;
        self.reconcile(&bindings).map_err(bad)?;
        if (
            opened.len(),
            opened.modified().ok(),
            opened.ctime(),
            opened.ctime_nsec(),
        ) != (
            after.len(),
            after.modified().ok(),
            after.ctime(),
            after.ctime_nsec(),
        ) || after.len() != bytes.len() as u64
        {
            return Err(bad(Reason::ChangedDuringRead));
        }
        // This detects tested mutations; stable metadata is not a snapshot proof.
        observer(ProbePoint::BeforePublish, relative);
        self.reconcile(&bindings).map_err(bad)?;
        Ok((
            Source {
                path: native(relative),
                hash: blake3::hash(&bytes).to_hex().to_string(),
                bytes,
            },
            bindings,
        ))
    }
}

pub fn capture(root: &Path, relative: &Path) -> Result<Source, Diagnostic> {
    capture_with_probe(root, relative, DEFAULT_READ_LIMIT, |_, _| {})
}

/// Compatibility with the original post-open deterministic hook.
pub fn capture_after_open(
    root: &Path,
    relative: &Path,
    observer: impl FnOnce(),
) -> Result<Source, Diagnostic> {
    let mut observer = Some(observer);
    capture_with_probe(root, relative, DEFAULT_READ_LIMIT, |stage, _| {
        if stage == ProbePoint::SourceOpened
            && let Some(observer) = observer.take()
        {
            observer();
        }
    })
}

pub fn capture_with_probe(
    root: &Path,
    relative: &Path,
    limit: usize,
    mut observer: impl FnMut(ProbePoint, &Path),
) -> Result<Source, Diagnostic> {
    if !valid_relative(relative) {
        return Err(diagnostic(relative, Reason::ReadFailed));
    }
    if let Some(reason) = Config::default().exclusion(relative) {
        return Err(diagnostic(relative, reason));
    }
    let root = Root::admit(root).map_err(|e| diagnostic(relative, failure(&e)))?;
    observer(ProbePoint::RootAdmitted, Path::new(""));
    root.capture(relative, limit, &mut observer)
        .map(|(source, _)| source)
}

pub fn inventory(root: &Path, config: &Config) -> io::Result<Inventory> {
    inventory_with_probe(root, config, DEFAULT_READ_LIMIT, |_, _| {})
}

pub fn inventory_with_probe(
    root: &Path,
    config: &Config,
    limit: usize,
    mut observer: impl FnMut(ProbePoint, &Path),
) -> io::Result<Inventory> {
    config.validate()?;
    let root = Root::admit(root)?;
    let mut result = Inventory {
        checkout_id: checkout_identity(&root.locator, &root.file.metadata()?),
        sources: Vec::new(),
        diagnostics: Vec::new(),
    };
    observer(ProbePoint::RootAdmitted, Path::new(""));
    let mut collected = Vec::new();
    let mut directories = Vec::new();
    walk(
        &root,
        &root.file,
        Path::new(""),
        config,
        limit,
        &mut observer,
        &mut collected,
        &mut directories,
        &mut result.diagnostics,
    );
    observer(ProbePoint::BeforePublish, Path::new(""));
    // Coverage includes empty directories/root, not just captured file names.
    // Changed membership is partial coverage; individually valid sources remain.
    for (path, expected_identity, expected_stamp) in directories {
        let current = if path.as_os_str().is_empty() {
            root.file.metadata().map_err(|e| failure(&e))
        } else {
            root.open(&path, true, &mut |_, _| {})
                .and_then(|(file, _)| file.metadata().map_err(|e| failure(&e)))
        };
        match current {
            Ok(metadata)
                if identity(&metadata) == expected_identity
                    && stamp(&metadata) == expected_stamp => {}
            Ok(_) => result
                .diagnostics
                .push(diagnostic(&path, Reason::ChangedDuringRead)),
            Err(reason) => result.diagnostics.push(diagnostic(&path, reason)),
        }
    }
    for (source, bindings) in collected {
        match root.reconcile(&bindings) {
            Ok(()) => result.sources.push(source),
            Err(reason) => result.diagnostics.push(Diagnostic {
                path: source.path,
                reason,
            }),
        }
    }
    if let Err(reason) = root.root_valid() {
        result.sources.clear();
        result.diagnostics.push(diagnostic(Path::new(""), reason));
    }
    result.sources.sort_by(|a, b| a.path.cmp(&b.path));
    result.diagnostics.sort_by(|a, b| a.path.cmp(&b.path));
    Ok(result)
}

#[allow(clippy::too_many_arguments)]
fn walk(
    root: &Root,
    directory: &fs::File,
    relative: &Path,
    config: &Config,
    limit: usize,
    observer: &mut impl FnMut(ProbePoint, &Path),
    collected: &mut Vec<(Source, Bindings)>,
    directories: &mut Vec<(PathBuf, Identity, Stamp)>,
    diagnostics: &mut Vec<Diagnostic>,
) {
    let before = match directory.metadata() {
        Ok(metadata) => (identity(&metadata), stamp(&metadata)),
        Err(error) => {
            diagnostics.push(diagnostic(relative, failure(&error)));
            return;
        }
    };
    directories.push((relative.to_path_buf(), before.0, before.1));
    observer(ProbePoint::DirectoryOpened, relative);
    let entries = match rustix::fs::Dir::read_from(directory) {
        Ok(entries) => entries,
        Err(error) => {
            diagnostics.push(diagnostic(relative, resolution_error(error)));
            return;
        }
    };
    for entry in entries {
        let entry = match entry {
            Ok(entry) => entry,
            Err(error) => {
                diagnostics.push(diagnostic(relative, resolution_error(error)));
                continue;
            }
        };
        let name = entry.file_name().to_bytes();
        if name == b"." || name == b".." {
            continue;
        }
        let name = Path::new(std::ffi::OsStr::from_bytes(name));
        let path = relative.join(name);
        if let Some(reason) = config.exclusion(&path) {
            diagnostics.push(diagnostic(&path, reason));
            continue;
        }
        let stat = match rustix::fs::statat(directory, name, rustix::fs::AtFlags::SYMLINK_NOFOLLOW)
        {
            Ok(stat) => stat,
            Err(error) => {
                diagnostics.push(diagnostic(&path, resolution_error(error)));
                continue;
            }
        };
        match rustix::fs::FileType::from_raw_mode(stat.st_mode) {
            rustix::fs::FileType::Symlink => diagnostics.push(diagnostic(&path, Reason::Symlink)),
            rustix::fs::FileType::Directory => match root.open_child(directory, name, true) {
                Ok(child) => {
                    // Validate each enumerated directory's binding before and after traversal.
                    let expected = child.metadata().map(|m| identity(&m));
                    let before = collected.len();
                    walk(
                        root,
                        &child,
                        &path,
                        config,
                        limit,
                        observer,
                        collected,
                        directories,
                        diagnostics,
                    );
                    let current = root.open(&path, true, &mut |_, _| {}).and_then(|(f, _)| {
                        f.metadata().map(|m| identity(&m)).map_err(|e| failure(&e))
                    });
                    if !matches!((expected, current), (Ok(a), Ok(b)) if a == b) {
                        collected.truncate(before);
                        diagnostics.push(diagnostic(&path, Reason::ChangedDuringRead));
                    }
                }
                Err(reason) => diagnostics.push(diagnostic(&path, reason)),
            },
            rustix::fs::FileType::RegularFile => match root.capture(&path, limit, observer) {
                Ok(source) => collected.push(source),
                Err(bad) => diagnostics.push(bad),
            },
            _ => diagnostics.push(diagnostic(&path, Reason::NonRegular)),
        }
    }
    match directory.metadata() {
        Ok(metadata) if (identity(&metadata), stamp(&metadata)) == before => (),
        Ok(_) => diagnostics.push(diagnostic(relative, Reason::ChangedDuringRead)),
        Err(error) => diagnostics.push(diagnostic(relative, failure(&error))),
    }
}

/// Read .gitfile as opaque bytes to identify an advisory worktree pointer.
/// The referenced path is deliberately never opened or used for state keys.
pub fn gitfile_pointer(root: &Path) -> io::Result<Option<Vec<u8>>> {
    let path = root.join(".git");
    match fs::symlink_metadata(&path) {
        Ok(metadata) if metadata.is_file() => {
            // Deliberately scoped advisory reader; normal source capture refuses .git.
            let source = Root::admit(root)?
                .capture(Path::new(".git"), DEFAULT_READ_LIMIT, &mut |_, _| {})
                .map_err(|d| io::Error::other(format!("gitfile: {:?}", d.reason)))?
                .0;
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
