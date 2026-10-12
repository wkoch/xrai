use std::process::{Command, Output};

fn invoke(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_xrai"))
        .args(args)
        .output()
        .expect("the built xrai executable should run")
}

#[test]
fn help_only_advertises_available_options() {
    let output = invoke(&["--help"]);
    assert!(output.status.success());
    assert!(output.stderr.is_empty());
    let help = String::from_utf8(output.stdout).unwrap();
    assert!(help.contains("Usage: xrai [OPTION]"));
    assert!(help.contains("--help"));
    assert!(help.contains("--version"));
    for future_operation in ["index", "search", "context", "mcp", "inspect", "expand"] {
        assert!(!help.contains(future_operation));
    }
    assert_eq!(invoke(&[]).stdout, help.as_bytes());
    assert_eq!(invoke(&["-h"]).stdout, help.as_bytes());
}

#[test]
fn version_reports_package_version_and_native_platform() {
    let output = invoke(&["--version"]);
    assert!(output.status.success());
    assert!(output.stderr.is_empty());
    assert_eq!(
        String::from_utf8(output.stdout).unwrap(),
        format!(
            "xrai {} ({}-{})\n",
            env!("CARGO_PKG_VERSION"),
            std::env::consts::ARCH,
            std::env::consts::OS
        )
    );
    assert_eq!(invoke(&["-V"]).stdout, invoke(&["--version"]).stdout);
}

#[test]
fn unsupported_operations_and_extra_arguments_fail_without_data() {
    for args in [
        vec!["index", "."],
        vec!["mcp"],
        vec!["--unknown"],
        vec!["--help", "--unknown"],
        vec!["--version", "extra"],
    ] {
        let output = invoke(&args);
        assert_eq!(output.status.code(), Some(2), "args: {args:?}");
        assert!(output.stdout.is_empty());
        assert!(String::from_utf8(output.stderr).unwrap().contains("--help"));
    }
}
