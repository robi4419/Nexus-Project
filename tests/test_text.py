import pytest

from transform.text import html_to_text


@pytest.mark.parametrize(
    ("html", "text"),
    [
        ("<p>We use <strong>Python</strong> &amp; SQL.</p>", "We use Python & SQL."),
        ("<ul><li>Docker</li><li>Kubernetes</li></ul>", "- Docker\n- Kubernetes"),
        ("Line one<br>Line two<br/>Line three", "Line one\nLine two\nLine three"),
        ("<h2>Requirements</h2><p>SQL</p>", "Requirements\n\nSQL"),
        ("<b>Python</b>,<b>SQL</b>", "Python , SQL"),
        ("a&nbsp;&nbsp;  b\t\tc", "a b c"),
        ("Use &lt;div&gt; tags", "Use <div> tags"),
        ("<P CLASS='x'>Upper-case tags</P>", "Upper-case tags"),
        ("<p>One</p>\n\n\n\n<p>Two</p>", "One\n\nTwo"),
        ("", ""),
    ],
)
def test_html_to_text(html, text):
    assert html_to_text(html) == text


def test_none_stays_none():
    assert html_to_text(None) is None


def test_real_jobicy_description(jobicy_page):
    description = jobicy_page["jobs"][1]["jobDescription"]

    assert html_to_text(description) == (
        "Made-up test job.\n\n"
        "- Build batch pipelines with Python and SQL\n"
        "- Orchestrate with Apache Airflow; model data with dbt on Databricks\n"
        "- Nice to have: Go, Kubernetes (k8s)"
    )
