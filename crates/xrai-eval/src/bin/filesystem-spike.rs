//! Native capability receipt; runs only in its newly created temporary directory.
use std::os::unix::{
    ffi::{OsStrExt, OsStringExt},
    fs::{PermissionsExt, symlink},
};
use std::{
    ffi::OsString,
    fs,
    path::PathBuf,
    process::Command,
    time::{SystemTime, UNIX_EPOCH},
};
use xrai_eval::filesystem_spike::{self as spike, Config, Reason};
struct Fixture(PathBuf);
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
fn quote(value: &str) -> String {
    let mut escaped = String::from("\"");
    for character in value.chars() {
        match character {
            '"' => escaped.push_str("\\\""),
            '\\' => escaped.push_str("\\\\"),
            '\n' => escaped.push_str("\\n"),
            '\r' => escaped.push_str("\\r"),
            '\t' => escaped.push_str("\\t"),
            c if c.is_control() => escaped.push_str(&format!("\\u{:04x}", c as u32)),
            c => escaped.push(c),
        }
    }
    escaped.push('"');
    escaped
}
fn run() -> Result<(), Box<dyn std::error::Error>> {
    let stamp = SystemTime::now().duration_since(UNIX_EPOCH)?.as_nanos();
    let fixture = Fixture(
        std::env::temp_dir().join(format!("xrai-fs-receipt-{}-{stamp}", std::process::id())),
    );
    fs::create_dir(&fixture.0)?;
    let root = fixture.0.join("checkout");
    fs::create_dir(&root)?;
    fs::write(root.join("Case.rs"), b"bytes\r\n\xff")?;
    let case_sensitive = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(root.join("case.rs"));
    let case_sensitive = match case_sensitive {
        Ok(_) => true,
        Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => false,
        Err(error) => return Err(error.into()),
    };
    fs::write(root.join("caf\u{00e9}.py"), b"NFC")?;
    let normalization_distinct = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(root.join("cafe\u{0301}.py"));
    let normalization_distinct = match normalization_distinct {
        Ok(_) => true,
        Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => false,
        Err(error) => return Err(error.into()),
    };
    let native_name = OsString::from_vec(b"space \xff.go".to_vec());
    let native_name_result = fs::write(root.join(&native_name), b"native\x00\r\n");
    let native_name_supported = native_name_result.is_ok();
    let native_name_error = native_name_result.err().map(|error| error.to_string());
    fs::write(root.join("denied"), b"secret")?;
    fs::set_permissions(root.join("denied"), fs::Permissions::from_mode(0o0))?;
    let permission_denial_supported = matches!(spike::capture(&root, std::path::Path::new("denied")), Err(d) if d.reason == Reason::PermissionDenied);
    fs::set_permissions(root.join("denied"), fs::Permissions::from_mode(0o600))?;
    fs::write(fixture.0.join("external"), b"outside")?;
    symlink("../external", root.join("link"))?;
    symlink(".", root.join("cycle"))?;
    let inventory = spike::inventory(&root, &Config::default())?;
    let sources = inventory
        .sources
        .iter()
        .map(|s| {
            format!(
                "{{\"path_hex\":{},\"hash\":{},\"bytes\":{}}}",
                quote(
                    &s.path
                        .iter()
                        .map(|b| format!("{b:02x}"))
                        .collect::<String>()
                ),
                quote(&s.hash),
                s.bytes.len()
            )
        })
        .collect::<Vec<_>>()
        .join(",");
    let diagnostics = inventory
        .diagnostics
        .iter()
        .map(|d| {
            format!(
                "{{\"path_hex\":{},\"reason\":{}}}",
                quote(
                    &d.path
                        .iter()
                        .map(|b| format!("{b:02x}"))
                        .collect::<String>()
                ),
                quote(&format!("{:?}", d.reason))
            )
        })
        .collect::<Vec<_>>()
        .join(",");
    let df = Command::new("df").arg("-P").arg(&root).output()?;
    let df_text = String::from_utf8_lossy(&df.stdout).into_owned();
    #[cfg(target_os = "linux")]
    let filesystem = Command::new("stat")
        .args(["--file-system", "--format=%T"])
        .arg(&root)
        .output()?;
    #[cfg(target_os = "macos")]
    let filesystem = Command::new("mount").output()?;
    let fs_text = String::from_utf8_lossy(&filesystem.stdout).into_owned();
    #[cfg(target_os = "macos")]
    let fs_text = {
        let device = df_text
            .lines()
            .nth(1)
            .and_then(|line| line.split_whitespace().next())
            .ok_or("df has no filesystem device")?;
        fs_text
            .lines()
            .filter(|line| line.starts_with(&format!("{device} on ")))
            .collect::<Vec<_>>()
            .join("\n")
    };
    let mut observed_names = fs::read_dir(&root)?
        .map(|e| {
            e.map(|e| {
                e.file_name()
                    .as_bytes()
                    .iter()
                    .map(|b| format!("{b:02x}"))
                    .collect::<String>()
            })
        })
        .collect::<Result<Vec<_>, _>>()?;
    observed_names.sort();
    println!(
        "{{\"schema\":\"xrai-filesystem-spike-receipt-v1\",\"os\":{},\"arch\":{},\"root_native_hex\":{},\"checkout_id\":{},\"case_sensitive\":{},\"normalization_distinct\":{},\"invalid_utf8_name_supported\":{},\"invalid_utf8_name_error\":{},\"permission_denial_supported\":{},\"df_exit_success\":{},\"df\":{},\"filesystem_probe_exit_success\":{},\"filesystem_probe\":{},\"filesystem_probe_stderr\":{},\"observed_names_hex\":[{}],\"sources\":[{}],\"diagnostics\":[{}]}}",
        quote(std::env::consts::OS),
        quote(std::env::consts::ARCH),
        quote(
            &root
                .as_os_str()
                .as_bytes()
                .iter()
                .map(|b| format!("{b:02x}"))
                .collect::<String>()
        ),
        quote(&inventory.checkout_id),
        case_sensitive,
        normalization_distinct,
        native_name_supported,
        native_name_error
            .as_deref()
            .map(quote)
            .unwrap_or_else(|| "null".into()),
        permission_denial_supported,
        df.status.success(),
        quote(&df_text),
        filesystem.status.success(),
        quote(&fs_text),
        quote(&String::from_utf8_lossy(&filesystem.stderr)),
        observed_names
            .iter()
            .map(|s| quote(s))
            .collect::<Vec<_>>()
            .join(","),
        sources,
        diagnostics
    );
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("filesystem spike failed: {error}");
        std::process::exit(1);
    }
}
