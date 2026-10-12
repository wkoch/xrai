#![cfg(any(target_os = "linux", target_os = "macos"))]
use std::os::unix::{fs::symlink, net::UnixListener};
use std::{
    fs,
    path::{Path, PathBuf},
    sync::atomic::{AtomicU64, Ordering},
};
use xrai_eval::filesystem_spike::{self as spike, Config, ProbePoint, Reason};
static SERIAL: AtomicU64 = AtomicU64::new(0);
struct Tree {
    base: PathBuf,
    root: PathBuf,
    outside: PathBuf,
}
impl Tree {
    fn new() -> Self {
        let base = std::env::temp_dir().join(format!(
            "xrai-anchored-{}-{}",
            std::process::id(),
            SERIAL.fetch_add(1, Ordering::Relaxed)
        ));
        let root = base.join("root");
        let outside = base.join("outside");
        fs::create_dir_all(root.join("nested")).unwrap();
        fs::create_dir_all(&outside).unwrap();
        fs::write(root.join("nested/source"), b"INSIDE").unwrap();
        fs::write(root.join("stable"), b"STABLE").unwrap();
        fs::write(outside.join("source"), b"EXTERNAL-SENTINEL").unwrap();
        Self {
            base,
            root,
            outside,
        }
    }
    fn replace_ancestor(&self) {
        fs::rename(self.root.join("nested"), self.base.join("moved")).unwrap();
        symlink(&self.outside, self.root.join("nested")).unwrap();
    }
}
impl Drop for Tree {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.base);
    }
}
fn source() -> &'static Path {
    Path::new("nested/source")
}

#[test]
fn rejects_invalid_native_components_and_internal_capture_inventory_exclusions() {
    let tree = Tree::new();
    for name in [
        "",
        "/stable",
        "./stable",
        "nested/../stable",
        "nested//source",
        "stable/",
        "a\0b",
    ] {
        assert_eq!(
            spike::capture(&tree.root, Path::new(name))
                .unwrap_err()
                .reason,
            Reason::ReadFailed
        );
    }
    for name in [".git/secret", ".xrai/state", "nested/.git/data"] {
        assert_eq!(
            spike::capture(&tree.root, Path::new(name))
                .unwrap_err()
                .reason,
            Reason::InternalState
        );
    }
    let inventory = spike::inventory(&tree.root, &Config::default()).unwrap();
    assert_eq!(inventory.sources.len(), 2);
}

#[test]
fn ancestor_symlink_before_open_never_delivers_external_sentinel() {
    let tree = Tree::new();
    let result = spike::capture_with_probe(&tree.root, source(), 1024, |stage, _| {
        if stage == ProbePoint::RootAdmitted {
            tree.replace_ancestor();
        }
    });
    assert_eq!(result.unwrap_err().reason, Reason::Symlink);
    assert_eq!(
        fs::read(tree.outside.join("source")).unwrap(),
        b"EXTERNAL-SENTINEL"
    );
}

#[test]
fn barrier_swap_after_ancestor_handle_open_invalidates_binding() {
    let tree = Tree::new();
    std::thread::scope(|scope| {
        let (admitted_tx, admitted_rx) = std::sync::mpsc::channel();
        let (done_tx, done_rx) = std::sync::mpsc::channel();
        let tree_ref = &tree;
        scope.spawn(move || {
            admitted_rx.recv().unwrap();
            tree_ref.replace_ancestor();
            done_tx.send(()).unwrap();
        });
        let result = spike::capture_with_probe(&tree.root, source(), 1024, |stage, _| {
            if stage == ProbePoint::AncestorOpened {
                admitted_tx.send(()).unwrap();
                done_rx.recv().unwrap();
            }
        });
        assert_eq!(result.unwrap_err().reason, Reason::Symlink);
    });
}

#[test]
fn ancestor_symlink_after_source_open_never_publishes_as_current() {
    let tree = Tree::new();
    let result = spike::capture_with_probe(&tree.root, source(), 1024, |stage, _| {
        if stage == ProbePoint::SourceOpened {
            tree.replace_ancestor();
        }
    });
    assert_eq!(result.unwrap_err().reason, Reason::Symlink);
}

#[test]
fn moving_open_directory_outside_without_link_is_diagnosed() {
    let tree = Tree::new();
    let result = spike::capture_with_probe(&tree.root, source(), 1024, |stage, _| {
        if stage == ProbePoint::AncestorOpened {
            fs::rename(tree.root.join("nested"), tree.outside.join("moved")).unwrap();
        }
    });
    assert_eq!(result.unwrap_err().reason, Reason::Removed);
}

#[test]
fn replaced_root_invalidates_all_inventory_sources() {
    let tree = Tree::new();
    let inventory =
        spike::inventory_with_probe(&tree.root, &Config::default(), 1024, |stage, path| {
            if stage == ProbePoint::BeforePublish && path.as_os_str().is_empty() {
                fs::rename(&tree.root, tree.base.join("old-root")).unwrap();
                fs::create_dir(&tree.root).unwrap();
                fs::write(tree.root.join("stable"), b"REPLACEMENT").unwrap();
            }
        })
        .unwrap();
    assert!(inventory.sources.is_empty());
    assert!(
        inventory
            .diagnostics
            .iter()
            .any(|d| d.reason == Reason::ChangedDuringRead)
    );
}

#[test]
fn anchored_enumeration_of_moved_directory_returns_partial_inventory() {
    let tree = Tree::new();
    let inventory =
        spike::inventory_with_probe(&tree.root, &Config::default(), 1024, |stage, path| {
            if stage == ProbePoint::DirectoryOpened && path == Path::new("nested") {
                tree.replace_ancestor();
            }
        })
        .unwrap();
    assert_eq!(inventory.sources.len(), 1);
    assert_eq!(inventory.sources[0].bytes, b"STABLE");
    assert!(
        inventory
            .diagnostics
            .iter()
            .any(|d| d.path == b"nested" && d.reason == Reason::ChangedDuringRead)
    );
    assert!(
        inventory
            .sources
            .iter()
            .all(|s| s.bytes != b"EXTERNAL-SENTINEL")
    );
}

#[test]
fn last_publication_reconciles_previously_captured_ancestor() {
    let tree = Tree::new();
    let inventory =
        spike::inventory_with_probe(&tree.root, &Config::default(), 1024, |stage, path| {
            if stage == ProbePoint::BeforePublish && path.as_os_str().is_empty() {
                tree.replace_ancestor();
            }
        })
        .unwrap();
    assert_eq!(inventory.sources.len(), 1);
    assert_eq!(inventory.sources[0].path, b"stable");
    assert!(
        inventory
            .diagnostics
            .iter()
            .any(|d| d.path == b"nested/source")
    );
}

#[test]
fn original_file_unlink_and_recreate_cannot_reuse_old_binding() {
    let tree = Tree::new();
    let result = spike::capture_with_probe(&tree.root, source(), 1024, |stage, _| {
        if stage == ProbePoint::SourceOpened {
            fs::remove_file(tree.root.join(source())).unwrap();
            fs::write(tree.root.join(source()), b"NEW").unwrap();
        }
    });
    assert_eq!(result.unwrap_err().reason, Reason::ChangedDuringRead);
}

#[test]
fn in_place_same_size_and_restored_mtime_is_not_a_snapshot_guarantee() {
    let tree = Tree::new();
    let path = tree.root.join(source());
    let original = fs::metadata(&path).unwrap().modified().unwrap();
    let result = spike::capture_with_probe(&tree.root, source(), 1024, |stage, _| {
        if stage == ProbePoint::SourceOpened {
            fs::write(&path, b"CHANGED".get(..6).unwrap()).unwrap();
            fs::File::options()
                .write(true)
                .open(&path)
                .unwrap()
                .set_times(fs::FileTimes::new().set_modified(original))
                .unwrap();
            assert_eq!(fs::metadata(&path).unwrap().modified().unwrap(), original);
        }
    });
    match result {
        Err(d) => assert_eq!(d.reason, Reason::ChangedDuringRead),
        Ok(s) => {
            // Coarse/unchanged metadata cannot prove coherence. If admitted,
            // the hash still describes exactly these delivered bytes.
            assert_eq!(s.bytes, b"CHANGE");
            assert_eq!(s.hash, blake3::hash(&s.bytes).to_hex().as_str());
        }
    }
}

#[test]
fn hard_link_captures_shared_object_and_does_not_claim_link_confinement() {
    let tree = Tree::new();
    fs::hard_link(tree.outside.join("source"), tree.root.join("hard-link")).unwrap();
    let value = spike::capture(&tree.root, Path::new("hard-link")).unwrap();
    assert_eq!(value.bytes, b"EXTERNAL-SENTINEL");
    assert_eq!(value.hash, blake3::hash(&value.bytes).to_hex().as_str());
}

#[test]
fn special_files_are_refused_without_fifo_blocking() {
    let tree = Tree::new();
    let _socket = UnixListener::bind(tree.root.join("socket")).unwrap();
    assert!(
        std::process::Command::new("mkfifo")
            .arg(tree.root.join("fifo"))
            .status()
            .unwrap()
            .success()
    );
    for name in ["socket", "fifo"] {
        assert_eq!(
            spike::capture(&tree.root, Path::new(name))
                .unwrap_err()
                .reason,
            Reason::NonRegular
        );
    }
    let inventory = spike::inventory(&tree.root, &Config::default()).unwrap();
    assert_eq!(inventory.sources.len(), 2);
    assert_eq!(
        inventory
            .diagnostics
            .iter()
            .filter(|d| d.reason == Reason::NonRegular)
            .count(),
        2
    );
}

#[test]
fn ceiling_is_enforced_for_initial_size_and_during_growth() {
    let tree = Tree::new();
    assert_eq!(
        spike::capture_with_probe(&tree.root, source(), 5, |_, _| {})
            .unwrap_err()
            .reason,
        Reason::LimitExceeded
    );
    fs::write(tree.root.join(source()), vec![b'x'; 8192]).unwrap();
    let result = spike::capture_with_probe(&tree.root, source(), 8192, |stage, _| {
        if stage == ProbePoint::ChunkRead {
            use std::io::Write;
            fs::File::options()
                .append(true)
                .open(tree.root.join(source()))
                .unwrap()
                .write_all(b"!")
                .unwrap();
        }
    });
    assert_eq!(result.unwrap_err().reason, Reason::LimitExceeded);
    let inventory =
        spike::inventory_with_probe(&tree.root, &Config::default(), 8, |_, _| {}).unwrap();
    assert_eq!(inventory.sources.len(), 1);
    assert_eq!(inventory.sources[0].bytes, b"STABLE");
    assert!(
        inventory
            .diagnostics
            .iter()
            .any(|d| d.reason == Reason::LimitExceeded)
    );
}

#[test]
fn stabilized_update_equals_independent_rebuild_and_old_bytes_remain_immutable() {
    let tree = Tree::new();
    let a = spike::inventory(&tree.root, &Config::default()).unwrap();
    fs::write(tree.root.join(source()), b"VERSION-B").unwrap();
    let incremental = spike::inventory(&tree.root, &Config::default()).unwrap();
    let rebuild = spike::inventory(&tree.root, &Config::default()).unwrap();
    assert_eq!(incremental.sources, rebuild.sources);
    assert_eq!(
        a.sources
            .iter()
            .find(|s| s.path == b"nested/source")
            .unwrap()
            .bytes,
        b"INSIDE"
    );
    assert!(
        incremental
            .sources
            .iter()
            .all(|s| s.hash == blake3::hash(&s.bytes).to_hex().as_str())
    );
}

#[test]
fn seeded_adversarial_schedule_supplements_deterministic_barriers() {
    let initial = 0x584e_5241_4902_u64;
    let mut seed = initial;
    for _ in 0..32 {
        seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1);
        let target = match seed % 4 {
            0 => ProbePoint::RootAdmitted,
            1 => ProbePoint::AncestorOpened,
            2 => ProbePoint::SourceOpened,
            _ => ProbePoint::BeforePublish,
        };
        let tree = Tree::new();
        let mut swapped = false;
        let result = spike::capture_with_probe(&tree.root, source(), 1024, |stage, _| {
            if stage == target && !swapped {
                tree.replace_ancestor();
                swapped = true;
            }
        });
        assert!(swapped);
        assert_eq!(result.unwrap_err().reason, Reason::Symlink);
    }
    println!(
        "filesystem_stress_seed={initial:#x} schedules=32 (finite hook scheduling, not exhaustive concurrent stress)"
    );
}

#[test]
#[cfg(target_os = "linux")]
fn existing_proc_mount_is_refused_by_linux_no_xdev() {
    use std::os::unix::fs::MetadataExt;
    assert_ne!(
        fs::metadata("/").unwrap().dev(),
        fs::metadata("/proc").unwrap().dev()
    );
    assert!(!fs::read("/proc/version").unwrap().is_empty());
    let error = spike::capture(Path::new("/"), Path::new("proc/version")).unwrap_err();
    assert_eq!(error.reason, Reason::MountBoundary);
    println!("mount_boundary=existing-proc no_xdev=refused (new mounts not created)");
}

#[test]
fn seeded_concurrent_writer_stress_never_delivers_external_sentinel() {
    let tree = Tree::new();
    let start = std::sync::Barrier::new(2);
    let initial = 0x4c33_4653_2026_u64;
    std::thread::scope(|scope| {
        scope.spawn(|| {
            start.wait();
            let mut seed = initial;
            for _ in 0..64 {
                seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1);
                fs::rename(tree.root.join("nested"), tree.root.join("held")).unwrap();
                symlink(&tree.outside, tree.root.join("nested")).unwrap();
                for _ in 0..(seed % 7) {
                    std::thread::yield_now();
                }
                fs::remove_file(tree.root.join("nested")).unwrap();
                fs::rename(tree.root.join("held"), tree.root.join("nested")).unwrap();
            }
        });
        start.wait();
        let mut accepted = 0;
        let mut rejected = 0;
        for _ in 0..128 {
            match spike::capture(&tree.root, source()) {
                Ok(s) => {
                    assert_eq!(s.bytes, b"INSIDE");
                    assert_eq!(s.hash, blake3::hash(&s.bytes).to_hex().as_str());
                    accepted += 1;
                }
                Err(_) => rejected += 1,
            }
        }
        println!(
            "concurrent_stress_seed={initial:#x} writer_rounds=64 captures=128 accepted={accepted} rejected={rejected}"
        );
    });
    assert_eq!(
        spike::capture(&tree.root, source()).unwrap().bytes,
        b"INSIDE"
    );
}

#[test]
fn inventory_final_reconciliation_rejects_changed_source_revision() {
    let tree = Tree::new();
    let inventory =
        spike::inventory_with_probe(&tree.root, &Config::default(), 1024, |stage, path| {
            if stage == ProbePoint::BeforePublish && path.as_os_str().is_empty() {
                fs::write(tree.root.join("stable"), b"LONGER-REVISION").unwrap();
            }
        })
        .unwrap();
    assert_eq!(inventory.sources.len(), 1);
    assert_eq!(inventory.sources[0].path, b"nested/source");
    assert!(
        inventory
            .diagnostics
            .iter()
            .any(|d| d.path == b"stable" && d.reason == Reason::ChangedDuringRead)
    );
}

#[test]
fn replacing_checkout_parent_with_alias_of_moved_parent_invalidates_locator() {
    let tree = Tree::new();
    let container = tree.base.join("container");
    fs::create_dir(&container).unwrap();
    let checkout = container.join("checkout");
    fs::create_dir(&checkout).unwrap();
    fs::write(checkout.join("source"), b"INSIDE").unwrap();
    let moved = tree.base.join("outside-container");
    let result = spike::capture_with_probe(&checkout, Path::new("source"), 1024, |stage, _| {
        if stage == ProbePoint::SourceOpened {
            fs::rename(&container, &moved).unwrap();
            symlink(&moved, &container).unwrap();
        }
    });
    assert!(matches!(
        result.unwrap_err().reason,
        Reason::Symlink | Reason::ChangedDuringRead
    ));
}

#[test]
fn new_file_after_enumeration_marks_root_coverage_partial() {
    let tree = Tree::new();
    let inventory =
        spike::inventory_with_probe(&tree.root, &Config::default(), 1024, |stage, path| {
            if stage == ProbePoint::BeforePublish && path.as_os_str().is_empty() {
                fs::write(tree.root.join("added-after-enumeration"), b"NEW").unwrap();
            }
        })
        .unwrap();
    assert!(
        inventory
            .diagnostics
            .iter()
            .any(|d| d.path.is_empty() && d.reason == Reason::ChangedDuringRead)
    );
    assert!(
        !inventory
            .sources
            .iter()
            .any(|s| s.path == b"added-after-enumeration")
    );
}

#[test]
fn empty_directory_addition_and_removal_are_reconciled_before_publication() {
    for addition in [true, false] {
        let tree = Tree::new();
        let empty = tree.root.join("empty");
        fs::create_dir(&empty).unwrap();
        let inventory =
            spike::inventory_with_probe(&tree.root, &Config::default(), 1024, |stage, path| {
                if stage == ProbePoint::BeforePublish && path.as_os_str().is_empty() {
                    if addition {
                        fs::write(empty.join("new"), b"NEW").unwrap();
                    } else {
                        fs::remove_dir(&empty).unwrap();
                    }
                }
            })
            .unwrap();
        assert!(inventory.diagnostics.iter().any(|d| d.path == b"empty"));
        assert!(inventory.sources.iter().all(|s| s.path != b"empty/new"));
    }
}
