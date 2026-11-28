import pytest

from ticket_assistant.sandbox import check

BAD = [
    "import os\nresult = 1",
    "result = open('x').read()",
    "result = df.__class__",
    "result = pd.read_csv('x')",
    "result = df.to_csv('x')",
    "result = eval('1')",
    "result = getattr(df, 'x')",
    "result = f'{df}'",
    "result = df.query('a > 1')",
    "x = 1",
]


@pytest.mark.parametrize("code", BAD)
def test_rejects(code):
    with pytest.raises(ValueError):
        check(code)


def test_accepts():
    check("d = df[df.created_year == 2024]\nresult = round(d.is_resolved.mean() * 100, 2)")