// Evaluator-only controlled contract. Never include in an agent workspace.
package convert

import (
	"context"
	"net/url"
	"reflect"
	"testing"

	access_model "code.gitea.io/gitea/models/perm/access"
	repo_model "code.gitea.io/gitea/models/repo"
	"code.gitea.io/gitea/models/unittest"
	"code.gitea.io/gitea/modules/util"
)

func xraiCheckPublicURL(t *testing.T, value string) {
	t.Helper()
	parsed, err := url.Parse(value)
	if err != nil {
		t.Fatalf("XRAI_CONTRACT_PARSE: %v", err)
	}
	if parsed.User != nil {
		t.Fatal("XRAI_CONTRACT_USERINFO: credentials remain")
	}
	want := url.Values{"branch": {"main", "release"}, "tokenizer": {"allowed"}, "oauth_token_hint": {"hint"}, "q": {"a+b c"}}
	if !reflect.DeepEqual(parsed.Query(), want) {
		t.Fatalf("XRAI_CONTRACT_SECRET_QUERY: got %v want %v", parsed.Query(), want)
	}
	if parsed.EscapedPath() != "/project%2Fname" || parsed.Fragment != "readme" {
		t.Fatal("XRAI_CONTRACT_COMPONENTS: path or fragment changed")
	}
}

const xraiPrivateURL = "https://alice:secret@git.example/project%2Fname?branch=main&ToKeN=private&branch=release&%61ccess_token=secret&ACCESS_TOKEN=again&PaSsWoRd=pwd&tokenizer=allowed&oauth_token_hint=hint&q=a%2Bb+c#readme"

func TestXraiContractHelper(t *testing.T) {
	value, err := util.SanitizeURL(xraiPrivateURL)
	if err != nil {
		t.Fatal(err)
	}
	xraiCheckPublicURL(t, value)
	for _, raw := range []string{"https://git.example/project?token=%zz", "https://git.example/project?%zz=secret"} {
		value, err = util.SanitizeURL(raw)
		if err == nil || value != "" {
			t.Fatalf("XRAI_CONTRACT_MALFORMED: got %q err %v", value, err)
		}
	}
}

func TestXraiContractModel(t *testing.T) {
	repo := &repo_model.Repository{OriginalURL: xraiPrivateURL}
	xraiCheckPublicURL(t, repo.SanitizedOriginalURL())
	if repo.OriginalURL != xraiPrivateURL {
		t.Fatal("XRAI_CONTRACT_STORAGE: source address mutated")
	}
}

func TestXraiContractAPI(t *testing.T) {
	if err := unittest.PrepareTestDatabase(); err != nil {
		t.Fatal(err)
	}
	repo := unittest.AssertExistsAndLoadBean(t, &repo_model.Repository{ID: 1})
	repo.OriginalURL = xraiPrivateURL
	api := ToRepo(context.Background(), repo, access_model.Permission{})
	if api == nil {
		t.Fatal("XRAI_CONTRACT_INFRASTRUCTURE: API conversion returned nil")
	}
	xraiCheckPublicURL(t, api.OriginalURL)
	if repo.OriginalURL != xraiPrivateURL {
		t.Fatal("XRAI_CONTRACT_STORAGE: source address mutated")
	}
}

func TestXraiRegressionOrdinaryURL(t *testing.T) {
	for _, raw := range []string{"https://git.example/repo?q=a%20b&q=c+d&x=1#frag", "https://git.example/repo?tokenizer=allowed&oauth_token_hint=hint", "ssh://git.example/repo", ""} {
		got, err := util.SanitizeURL(raw)
		if err != nil || got != raw {
			t.Fatalf("XRAI_REGRESSION_ORDINARY: %q became %q (%v)", raw, got, err)
		}
	}
	repo := &repo_model.Repository{}
	if repo.SanitizedOriginalURL() != "" {
		t.Fatal("XRAI_REGRESSION_EMPTY: model changed")
	}
}

func TestXraiRegressionUserinfoAndInvalidURL(t *testing.T) {
	got, err := util.SanitizeURL("https://alice:secret@git.example/repo?branch=main#frag")
	if err != nil || got != "https://git.example/repo?branch=main#frag" {
		t.Fatalf("XRAI_REGRESSION_USERINFO: %q (%v)", got, err)
	}
	got, err = util.SanitizeURL("https://git.example/%zz")
	if err == nil || got != "" {
		t.Fatalf("XRAI_REGRESSION_INVALID: %q (%v)", got, err)
	}
}
