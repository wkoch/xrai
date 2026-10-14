//! Native validation boundary. DTOs are untrusted; ValidatedDiff is not Deserialize.
use super::{Anchor, Hunk, Input, hash};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::collections::{BTreeMap, BTreeSet};
pub const PROFILE: &str = "store-validated-diff.v1";
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(tag = "state", rename_all = "snake_case", deny_unknown_fields)]
pub enum Presence {
    Present { bytes_hex: String },
    Absent,
    Unavailable { reason: String },
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct RevisionInput {
    pub external_revision: String,
    pub frontend: String,
    pub root: String,
    pub edition: String,
    pub configuration: BTreeMap<String, String>,
    pub rules: String,
    #[serde(deserialize_with = "unique_files")]
    pub files: BTreeMap<String, Presence>,
    pub capture_blake3: String,
}
fn unique_files<'de, D: serde::Deserializer<'de>>(
    d: D,
) -> Result<BTreeMap<String, Presence>, D::Error> {
    struct Unique;
    impl<'de> serde::de::Visitor<'de> for Unique {
        type Value = BTreeMap<String, Presence>;
        fn expecting(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            f.write_str("unique bounded presence map")
        }
        fn visit_map<A: serde::de::MapAccess<'de>>(
            self,
            mut map: A,
        ) -> Result<Self::Value, A::Error> {
            let mut out = BTreeMap::new();
            while let Some((key, value)) = map.next_entry()? {
                if out.len() >= 4096 || out.insert(key, value).is_some() {
                    return Err(serde::de::Error::custom("duplicate or excessive file"));
                }
            }
            Ok(out)
        }
    }
    d.deserialize_map(Unique)
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Edit {
    pub base_span: [usize; 2],
    pub head_span: [usize; 2],
    pub removed_hex: String,
    pub replacement_hex: String,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Change {
    pub path: String,
    pub kind: String,
    pub hunks: Vec<Edit>,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct DiffInput {
    pub base: RevisionInput,
    pub head: RevisionInput,
    pub changes: Vec<Change>,
}
#[derive(Clone)]
pub(crate) struct Revision {
    pub dto: RevisionInput,
    pub input: Input,
}
/// Construction is private. The native check includes complete HEAD and presence;
/// external_revision is provenance, while capture_blake3 is actually checked.
#[derive(Clone)]
pub struct ValidatedDiff {
    pub(crate) base: Revision,
    pub(crate) head: Revision,
    pub(crate) changes: Vec<Change>,
    pub(crate) anchors: Vec<Anchor>,
    pub(crate) hunks: Vec<Hunk>,
}
pub fn unhex(value: &str) -> Result<Vec<u8>, String> {
    if !value.len().is_multiple_of(2)
        || value.len() > 16 * 1024 * 1024
        || !value
            .bytes()
            .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
    {
        return Err("invalid_diff:hex".into());
    }
    value
        .as_bytes()
        .as_chunks::<2>()
        .0
        .iter()
        .map(|pair| {
            u8::from_str_radix(
                std::str::from_utf8(pair).map_err(|_| "invalid_diff:hex")?,
                16,
            )
            .map_err(|_| "invalid_diff:hex".into())
        })
        .collect()
}
impl RevisionInput {
    /// Hash BLAKE3 over compact serde_json Value of this array (object keys sorted).
    pub fn identity(&self) -> String {
        hash(
            &serde_json::to_vec(&json!([
                self.external_revision,
                self.frontend,
                self.root,
                self.edition,
                self.configuration,
                self.rules,
                self.files
            ]))
            .expect("typed capture"),
        )
    }
    fn validate(self) -> Result<Revision, String> {
        if self.external_revision.is_empty()
            || self.external_revision.len() > 256
            || !["rust", "bytes"].contains(&self.frontend.as_str())
            || serde_json::to_vec(&self.configuration)
                .map_err(|e| e.to_string())?
                .len()
                > 8192
            || self.rules.len() > 256
            || self.root.len() > 4096
            || self.edition.len() > 16
            || self.capture_blake3 != self.identity()
        {
            return Err("invalid_diff:capture_identity_or_profile".into());
        }
        if self.frontend == "rust"
            && (!["2021", "2024"].contains(&self.edition.as_str())
                || ![
                    crate::semantics_spike::RULES,
                    crate::semantics_spike::RULES_R3,
                ]
                .contains(&self.rules.as_str()))
        {
            return Err("invalid_diff:rust_profile".into());
        }
        let mut files = BTreeMap::new();
        let mut total = 0usize;
        for (path, presence) in &self.files {
            if path.is_empty()
                || path.len() > 4096
                || path.starts_with('/')
                || path.contains(['\\', ':'])
                || path.split('/').any(|part| ["", ".", ".."].contains(&part))
                || path.chars().any(|c| c.is_control())
            {
                return Err("invalid_diff:path".into());
            }
            match presence {
                Presence::Present { bytes_hex } => {
                    let bytes = unhex(bytes_hex)?;
                    total = total
                        .checked_add(bytes.len())
                        .ok_or("invalid_diff:source_limit")?;
                    if total > super::MAX_RETAINED_BYTES {
                        return Err("invalid_diff:source_limit".into());
                    }
                    files.insert(
                        path.clone(),
                        String::from_utf8(bytes).map_err(|_| "invalid_diff:utf8")?,
                    );
                }
                Presence::Absent => {}
                Presence::Unavailable { .. } => {
                    return Err("invalid_diff:source_unavailable".into());
                }
            }
        }
        if self.frontend == "rust" && !files.contains_key(&self.root) {
            return Err("invalid_diff:rust_root_unavailable".into());
        }
        let input = Input {
            files,
            root: self.root.clone(),
            edition: self.edition.clone(),
            configuration: self.configuration.clone(),
            rules: self.rules.clone(),
        };
        Ok(Revision { dto: self, input })
    }
}
impl TryFrom<DiffInput> for ValidatedDiff {
    type Error = String;
    fn try_from(dto: DiffInput) -> Result<Self, String> {
        let base = dto.base.validate()?;
        let head = dto.head.validate()?;
        if base.dto.capture_blake3 == head.dto.capture_blake3
            || base.dto.frontend != head.dto.frontend
            || base.dto.root != head.dto.root
            || base.dto.edition != head.dto.edition
            || base.dto.configuration != head.dto.configuration
            || base.dto.rules != head.dto.rules
        {
            return Err("invalid_diff:revision_binding".into());
        }
        if base.dto.files.keys().ne(head.dto.files.keys()) || dto.changes.len() > 128 {
            return Err("invalid_diff:presence_universe".into());
        }
        let mut rebuilt = base.input.files.clone();
        let mut seen = BTreeSet::new();
        let mut anchors = vec![];
        let mut hunks = vec![];
        for change in &dto.changes {
            if !seen.insert(change.path.clone())
                || !base.dto.files.contains_key(&change.path)
                || change.hunks.is_empty()
            {
                return Err("invalid_diff:change".into());
            }
            let bp = base.input.files.contains_key(&change.path);
            let hp = head.input.files.contains_key(&change.path);
            if (bp, hp)
                != match change.kind.as_str() {
                    "create" => (false, true),
                    "delete" => (true, false),
                    "modify" => (true, true),
                    _ => return Err("invalid_diff:kind".into()),
                }
            {
                return Err("invalid_diff:presence".into());
            }
            let a = base
                .input
                .files
                .get(&change.path)
                .map(String::as_str)
                .unwrap_or("");
            let b = head
                .input
                .files
                .get(&change.path)
                .map(String::as_str)
                .unwrap_or("");
            let mut cursor = 0;
            let mut out = String::new();
            for edit in &change.hunks {
                if hunks.len() >= 4096 {
                    return Err("invalid_diff:hunk_limit".into());
                }
                let [s, e] = edit.base_span;
                let [u, v] = edit.head_span;
                if s < cursor || !super::valid_span(a, s, e) || !super::valid_span(b, u, v) {
                    return Err("invalid_diff:span".into());
                }
                let removed = String::from_utf8(unhex(&edit.removed_hex)?)
                    .map_err(|_| "invalid_diff:utf8")?;
                let added = String::from_utf8(unhex(&edit.replacement_hex)?)
                    .map_err(|_| "invalid_diff:utf8")?;
                if a[s..e] != removed || b[u..v] != added {
                    return Err("invalid_diff:hunk_bytes".into());
                }
                out.push_str(&a[cursor..s]);
                if out.len() != u {
                    return Err("invalid_diff:head_range".into());
                }
                out.push_str(&added);
                if out.len() != v {
                    return Err("invalid_diff:head_range".into());
                }
                cursor = e;
                for (present, side, start, end) in [(bp, "base", s, e), (hp, "head", u, v)] {
                    if present && start != end {
                        anchors.push(Anchor {
                            side: side.into(),
                            path: change.path.clone(),
                            start,
                            end,
                            lookup: None,
                        });
                    }
                }
                hunks.push(Hunk {
                    path: change.path.clone(),
                    base_start: s,
                    base_end: e,
                    head_start: u,
                    head_end: v,
                    removed,
                    added,
                });
            }
            out.push_str(&a[cursor..]);
            if out != b {
                return Err("invalid_diff:file_reconstruction".into());
            }
            if hp {
                rebuilt.insert(change.path.clone(), out);
            } else {
                rebuilt.remove(&change.path);
            }
        }
        if rebuilt != head.input.files {
            return Err("invalid_diff:integral_head".into());
        }
        Ok(Self {
            base,
            head,
            changes: dto.changes,
            anchors,
            hunks,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn revision(name: &str, source: &str) -> RevisionInput {
        let mut dto = RevisionInput {
            external_revision: name.into(),
            frontend: "bytes".into(),
            root: "a.jsx".into(),
            edition: "none".into(),
            configuration: BTreeMap::from([("capture".into(), "frozen".into())]),
            rules: "captured-bytes-v1".into(),
            files: BTreeMap::from([(
                "a.jsx".into(),
                Presence::Present {
                    bytes_hex: super::super::hex(source.as_bytes()),
                },
            )]),
            capture_blake3: String::new(),
        };
        dto.capture_blake3 = dto.identity();
        dto
    }
    fn diff() -> DiffInput {
        DiffInput {
            base: revision("A", "é\na\n"),
            head: revision("B", "é\nb\n"),
            changes: vec![Change {
                path: "a.jsx".into(),
                kind: "modify".into(),
                hunks: vec![Edit {
                    base_span: [3, 5],
                    head_span: [3, 5],
                    removed_hex: "610a".into(),
                    replacement_hex: "620a".into(),
                }],
            }],
        }
    }
    #[test]
    fn complete_head_and_utf8_are_native_requirements() {
        assert!(ValidatedDiff::try_from(diff()).is_ok());
        let mut v = diff();
        v.changes[0].hunks[0].base_span = [1, 5];
        assert!(ValidatedDiff::try_from(v).is_err());
        let mut v = diff();
        v.head = revision("B", "x\nb\n");
        assert!(ValidatedDiff::try_from(v).is_err());
        let mut v = diff();
        v.changes.clear();
        assert_eq!(
            ValidatedDiff::try_from(v).err().unwrap(),
            "invalid_diff:integral_head"
        );
    }
    #[test]
    fn presence_is_distinct_and_unavailable_cannot_be_complete() {
        let mut v = diff();
        v.base.files.insert("a.jsx".into(), Presence::Absent);
        v.base.capture_blake3 = v.base.identity();
        assert!(ValidatedDiff::try_from(v).is_err());
        let mut v = diff();
        v.base.files.insert(
            "a.jsx".into(),
            Presence::Unavailable {
                reason: "not captured".into(),
            },
        );
        v.base.capture_blake3 = v.base.identity();
        assert_eq!(
            ValidatedDiff::try_from(v).err().unwrap(),
            "invalid_diff:source_unavailable"
        );
        let mut v = diff();
        v.base.files.insert(
            "a.jsx".into(),
            Presence::Present {
                bytes_hex: "ff".into(),
            },
        );
        v.base.capture_blake3 = v.base.identity();
        assert_eq!(
            ValidatedDiff::try_from(v).err().unwrap(),
            "invalid_diff:utf8"
        );
    }
    #[test]
    fn identity_unknown_fields_and_duplicate_files_are_refused() {
        let mut v = diff();
        v.head.capture_blake3 = "0".repeat(64);
        assert!(ValidatedDiff::try_from(v).is_err());
        let mut value = serde_json::to_value(diff()).unwrap();
        value["private_oracle"] = json!("hidden");
        assert!(serde_json::from_value::<DiffInput>(value).is_err());
        let text = serde_json::to_string(&diff()).unwrap().replace(
            "\"files\":{",
            "\"files\":{\"a.jsx\":{\"state\":\"absent\"},",
        );
        assert!(serde_json::from_str::<DiffInput>(&text).is_err());
    }
}
