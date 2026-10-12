#![cfg(any(target_os = "linux", target_os = "macos"))]
use std::os::unix::{
    ffi::{OsStrExt, OsStringExt},
    fs::{PermissionsExt, symlink},
};
use std::{
    ffi::OsString,
    fs,
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
    time::{SystemTime, UNIX_EPOCH},
};
use xrai_eval::filesystem_spike::{self as spike, Config, Reason};
static SERIAL: AtomicU64 = AtomicU64::new(0);
struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "xrai-fs-{}-{stamp}-{}",
            std::process::id(),
            SERIAL.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).unwrap();
        Self(path)
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

#[test]
fn no_git_and_identical_named_checkouts_have_independent_writable_state() {
    let fixture = Fixture::new();
    let a = fixture.0.join("a/project");
    let b = fixture.0.join("b/project");
    fs::create_dir_all(&a).unwrap();
    fs::create_dir_all(&b).unwrap();
    for root in [&a, &b] {
        fs::write(root.join("same.rs"), b"fn same() {}\n").unwrap();
    }
    let first = spike::inventory(&a, &Config::default()).unwrap();
    let second = spike::inventory(&b, &Config::default()).unwrap();
    assert_eq!(first.sources, second.sources);
    assert_ne!(first.checkout_id, second.checkout_id);
    assert_eq!(spike::gitfile_pointer(&a).unwrap(), None);
    let cache = fixture.0.join("cache");
    let acache = spike::state_directory(&cache, &a).unwrap();
    let bcache = spike::state_directory(&cache, &b).unwrap();
    assert_ne!(acache, bcache);
    for cache in [&acache, &bcache] {
        fs::create_dir_all(cache).unwrap();
    }
    fs::write(acache.join("state"), b"A").unwrap();
    fs::write(bcache.join("state"), b"B").unwrap();
    assert_eq!(fs::read(acache.join("state")).unwrap(), b"A");
    assert_eq!(fs::read(bcache.join("state")).unwrap(), b"B");
}

#[test]
fn linked_worktrees_preserve_separate_identity_and_exclude_gitfile() {
    let fixture = Fixture::new();
    let a = fixture.0.join("worktree-a");
    let b = fixture.0.join("worktree-b");
    for root in [&a, &b] {
        fs::create_dir(root).unwrap();
        fs::write(
            root.join(".git"),
            b"gitdir: ../shared/.git/worktrees/test\r\n",
        )
        .unwrap();
        fs::write(root.join("file"), b"source").unwrap();
    }
    assert_eq!(
        spike::gitfile_pointer(&a).unwrap().unwrap(),
        b"../shared/.git/worktrees/test"
    );
    assert_ne!(
        spike::checkout_id(&a).unwrap(),
        spike::checkout_id(&b).unwrap()
    );
    let inventory = spike::inventory(&a, &Config::default()).unwrap();
    assert_eq!(inventory.sources.len(), 1);
    assert!(
        inventory
            .diagnostics
            .iter()
            .any(|d| d.path == b".git" && d.reason == Reason::InternalState)
    );
}

#[test]
fn unicode_spaces_invalid_utf8_and_crlf_preserve_native_and_source_bytes() {
    let fixture = Fixture::new();
    let names: Vec<Vec<u8>> = vec!["espaço λ.py".as_bytes().to_vec(), b"bad-\xff.rs".to_vec()];
    let bytes = b"line\r\nutf8: \xce\xbb\r\ninvalid: \xff\x00";
    let mut accepted = Vec::new();
    for name in &names {
        let native = OsString::from_vec(name.clone());
        assert_eq!(native.as_os_str().as_bytes(), name);
        match fs::write(fixture.0.join(&native), bytes) {
            Ok(()) => accepted.push(name.clone()),
            Err(error) => {
                assert_eq!(std::env::consts::OS, "macos");
                assert!(name.contains(&0xff));
                // Filesystem/OS versions map filename rejection to different
                // ErrorKind/errno values. Observe the capability, not a whitelist.
                // Positive writes and reads before and after the failed probe
                // distinguish filename rejection from an unusable directory.
                assert!(accepted.contains(&names[0]));
                let control = fixture.0.join(OsString::from_vec(names[0].clone()));
                assert_eq!(fs::read(&control).unwrap(), bytes);
                fs::write(&control, bytes).unwrap();
                assert_eq!(fs::read(&control).unwrap(), bytes);
                println!(
                    "invalid_utf8_filename_supported=false kind={:?} raw_os_error={:?}: {error}",
                    error.kind(),
                    error.raw_os_error()
                );
            }
        }
    }
    let inventory = spike::inventory(&fixture.0, &Config::default()).unwrap();
    assert_eq!(inventory.sources.len(), accepted.len());
    for name in &accepted {
        let source = inventory.sources.iter().find(|s| s.path == *name).unwrap();
        assert_eq!(source.bytes, bytes);
        assert_eq!(source.hash, blake3::hash(bytes).to_hex().as_str());
    }
    let bad = b"bad-\xff.rs";
    assert_ne!(bad.as_slice(), String::from_utf8_lossy(bad).as_bytes());
    if std::env::consts::OS == "linux" {
        assert_eq!(accepted.len(), 2);
    }
}

#[test]
fn filesystem_case_capability_is_observed_and_names_are_not_lowercased() {
    let fixture = Fixture::new();
    fs::write(fixture.0.join("Case.rs"), b"Upper").unwrap();
    let second = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(fixture.0.join("case.rs"));
    let case_sensitive = match second {
        Ok(_) => true,
        Err(error) => {
            assert_eq!(error.kind(), std::io::ErrorKind::AlreadyExists);
            false
        }
    };
    if case_sensitive {
        fs::write(fixture.0.join("case.rs"), b"lower").unwrap();
    }
    let inventory = spike::inventory(&fixture.0, &Config::default()).unwrap();
    assert_eq!(inventory.sources.len(), if case_sensitive { 2 } else { 1 });
    assert!(inventory.sources.iter().any(|s| s.path == b"Case.rs"));
    if case_sensitive {
        assert!(
            inventory
                .sources
                .iter()
                .any(|s| s.path == b"case.rs" && s.bytes == b"lower")
        );
    }
    println!("case_sensitive={case_sensitive}");
}

#[test]
fn symlink_escape_inside_link_and_cycle_are_explained_and_never_read() {
    let fixture = Fixture::new();
    let root = fixture.0.join("root");
    fs::create_dir(&root).unwrap();
    fs::write(fixture.0.join("outside"), b"secret-outside").unwrap();
    fs::write(root.join("inside"), b"allowed").unwrap();
    symlink("../outside", root.join("escape")).unwrap();
    symlink("inside", root.join("alias")).unwrap();
    symlink(".", root.join("loop")).unwrap();
    symlink("../", root.join("parent")).unwrap();
    let inventory = spike::inventory(&root, &Config::default()).unwrap();
    assert_eq!(inventory.sources.len(), 1);
    assert_eq!(inventory.sources[0].bytes, b"allowed");
    assert_eq!(inventory.diagnostics.len(), 4);
    assert!(
        inventory
            .diagnostics
            .iter()
            .all(|d| d.reason == Reason::Symlink)
    );
    assert_eq!(
        spike::capture(&root, std::path::Path::new("parent/outside"))
            .unwrap_err()
            .reason,
        Reason::Symlink
    );
    assert_eq!(
        spike::capture(&root, std::path::Path::new("../outside"))
            .unwrap_err()
            .reason,
        Reason::ReadFailed
    );
}

#[test]
fn explicit_exclusions_have_reason_and_internal_state_takes_precedence() {
    let fixture = Fixture::new();
    for name in [".git", ".xrai", "generated", "production"] {
        fs::create_dir(fixture.0.join(name)).unwrap();
        fs::write(fixture.0.join(name).join("data"), b"data").unwrap();
    }
    let config = Config {
        excluded_subtrees: vec![PathBuf::from("generated"), PathBuf::from(".git")],
    };
    let inventory = spike::inventory(&fixture.0, &config).unwrap();
    assert_eq!(inventory.sources.len(), 1);
    assert_eq!(inventory.sources[0].path, b"production/data");
    assert!(
        inventory
            .diagnostics
            .iter()
            .any(|d| d.path == b"generated" && d.reason == Reason::ConfigExcluded)
    );
    assert!(
        inventory
            .diagnostics
            .iter()
            .filter(|d| d.path == b".git" || d.path == b".xrai")
            .all(|d| d.reason == Reason::InternalState)
    );
}

#[test]
fn invalid_configuration_fails_before_inventory() {
    let fixture = Fixture::new();
    for path in ["", "/absolute", "../outside", "x/../../outside"] {
        let result = spike::inventory(
            &fixture.0,
            &Config {
                excluded_subtrees: vec![PathBuf::from(path)],
            },
        );
        assert_eq!(result.unwrap_err().kind(), std::io::ErrorKind::InvalidInput);
    }
}

#[test]
fn same_size_and_mtime_change_is_detected_by_content_hash() {
    let fixture = Fixture::new();
    let path = fixture.0.join("source");
    fs::write(&path, b"AAAA").unwrap();
    let before = fs::metadata(&path).unwrap();
    let first = spike::capture(&fixture.0, std::path::Path::new("source")).unwrap();
    fs::write(&path, b"BBBB").unwrap();
    let file = fs::File::options().write(true).open(&path).unwrap();
    file.set_times(
        fs::FileTimes::new()
            .set_modified(before.modified().unwrap())
            .set_accessed(before.accessed().unwrap()),
    )
    .unwrap();
    let after = fs::metadata(&path).unwrap();
    assert_eq!(before.len(), after.len());
    assert_eq!(before.modified().unwrap(), after.modified().unwrap());
    let second = spike::capture(&fixture.0, std::path::Path::new("source")).unwrap();
    assert_ne!(first.hash, second.hash);
    assert_eq!(second.bytes, b"BBBB");
}

#[test]
fn removal_between_discovery_and_capture_has_typed_diagnostic() {
    let fixture = Fixture::new();
    let path = fixture.0.join("removed");
    fs::write(&path, b"source").unwrap();
    assert!(fs::symlink_metadata(&path).unwrap().is_file());
    fs::remove_file(path).unwrap();
    let error = spike::capture(&fixture.0, std::path::Path::new("removed")).unwrap_err();
    assert_eq!(error.reason, Reason::Removed);
    assert_eq!(error.path, b"removed");
}

#[test]
fn permission_failure_is_diagnostic_or_records_privileged_capability() {
    let fixture = Fixture::new();
    let path = fixture.0.join("denied");
    fs::write(&path, b"source").unwrap();
    fs::set_permissions(&path, fs::Permissions::from_mode(0o0)).unwrap();
    let result = spike::capture(&fixture.0, std::path::Path::new("denied"));
    fs::set_permissions(&path, fs::Permissions::from_mode(0o600)).unwrap();
    match result {
        Err(error) => {
            assert_eq!(error.reason, Reason::PermissionDenied);
            println!("permission_denial_supported=true");
        }
        Ok(_) => {
            println!(
                "permission_denial_supported=false (runner can read mode 000; not evidence for denial)"
            );
        }
    }
}

#[test]
fn gitfile_symlinks_and_invalid_pointers_cannot_load_external_metadata() {
    let fixture = Fixture::new();
    let root = fixture.0.join("root");
    fs::create_dir(&root).unwrap();
    fs::write(fixture.0.join("outside"), b"gitdir: /external\n").unwrap();
    symlink("../outside", root.join(".git")).unwrap();
    assert_eq!(spike::gitfile_pointer(&root).unwrap(), None);
    fs::remove_file(root.join(".git")).unwrap();
    for bytes in [
        b"nonsense".as_slice(),
        b"gitdir: \n",
        b"gitdir: first\nsecond\n",
    ] {
        fs::write(root.join(".git"), bytes).unwrap();
        assert_eq!(
            spike::gitfile_pointer(&root).unwrap_err().kind(),
            std::io::ErrorKind::InvalidData
        );
    }
}

#[test]
fn actual_git_linked_worktrees_have_independent_checkout_state() {
    let fixture = Fixture::new();
    let repo = fixture.0.join("repo");
    let linked = fixture.0.join("linked");
    let git = |cwd: &std::path::Path, args: &[&std::ffi::OsStr]| {
        let output = std::process::Command::new("git")
            .current_dir(cwd)
            .env("GIT_CONFIG_GLOBAL", "/dev/null")
            .env("GIT_CONFIG_NOSYSTEM", "1")
            .env("GIT_AUTHOR_NAME", "Filesystem spike")
            .env("GIT_AUTHOR_EMAIL", "spike@example.invalid")
            .env("GIT_COMMITTER_NAME", "Filesystem spike")
            .env("GIT_COMMITTER_EMAIL", "spike@example.invalid")
            .args(["-c", "core.hooksPath=/dev/null"])
            .args(args)
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "git fixture failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
    };
    git(
        &fixture.0,
        &["init".as_ref(), "--quiet".as_ref(), repo.as_os_str()],
    );
    fs::write(repo.join("source.rs"), b"fn same() {}\n").unwrap();
    git(&repo, &["add".as_ref(), "source.rs".as_ref()]);
    git(
        &repo,
        &[
            "commit".as_ref(),
            "--quiet".as_ref(),
            "-m".as_ref(),
            "fixture".as_ref(),
        ],
    );
    git(
        &repo,
        &[
            "worktree".as_ref(),
            "add".as_ref(),
            "--quiet".as_ref(),
            "--detach".as_ref(),
            linked.as_os_str(),
        ],
    );
    let a = spike::inventory(&repo, &Config::default()).unwrap();
    let b = spike::inventory(&linked, &Config::default()).unwrap();
    assert_eq!(a.sources, b.sources);
    assert_ne!(a.checkout_id, b.checkout_id);
    assert!(
        spike::gitfile_pointer(&linked)
            .unwrap()
            .unwrap()
            .ends_with(b"/.git/worktrees/linked")
    );
    assert_ne!(
        spike::state_directory(&fixture.0.join("cache"), &repo).unwrap(),
        spike::state_directory(&fixture.0.join("cache"), &linked).unwrap()
    );
}

#[test]
fn removal_after_open_is_reported_even_when_unix_descriptor_remains_readable() {
    let fixture = Fixture::new();
    let path = fixture.0.join("removed-while-reading");
    fs::write(&path, b"source remains on the open descriptor").unwrap();
    let result = spike::capture_after_open(
        &fixture.0,
        std::path::Path::new("removed-while-reading"),
        || fs::remove_file(&path).unwrap(),
    );
    assert_eq!(result.unwrap_err().reason, Reason::Removed);
}

#[test]
fn replacement_after_open_is_a_diagnostic_instead_of_misattributed_source() {
    let fixture = Fixture::new();
    let path = fixture.0.join("replaced");
    fs::write(&path, b"first").unwrap();
    let result = spike::capture_after_open(&fixture.0, std::path::Path::new("replaced"), || {
        fs::remove_file(&path).unwrap();
        fs::write(&path, b"other").unwrap();
    });
    assert_eq!(result.unwrap_err().reason, Reason::ChangedDuringRead);
}
