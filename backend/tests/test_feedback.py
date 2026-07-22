# Обратная связь по AI-подборкам (задача 26): ставим/меняем/снимаем 👍/👎,
# читаем состояние, считаем сводку Claude vs ChatGPT.
REF = "atmosphere:1:music:Claude"


def test_feedback_empty_at_start(client):
    assert client.get("/api/v1/feedback").json() == {"feedback": {}}


def test_set_and_read_feedback(client):
    r = client.post("/api/v1/feedback", json={"ref": REF, "verdict": "up", "source": "Claude"})
    assert r.json() == {"ref": REF, "verdict": "up"}
    assert client.get("/api/v1/feedback").json() == {"feedback": {REF: "up"}}


def test_toggle_off_same_verdict(client):
    client.post("/api/v1/feedback", json={"ref": REF, "verdict": "up", "source": "Claude"})
    # повторный тот же вердикт — снимает оценку
    r = client.post("/api/v1/feedback", json={"ref": REF, "verdict": "up", "source": "Claude"})
    assert r.json() == {"ref": REF, "verdict": None}
    assert client.get("/api/v1/feedback").json() == {"feedback": {}}


def test_switch_verdict(client):
    client.post("/api/v1/feedback", json={"ref": REF, "verdict": "up", "source": "Claude"})
    r = client.post("/api/v1/feedback", json={"ref": REF, "verdict": "down", "source": "Claude"})
    assert r.json() == {"ref": REF, "verdict": "down"}
    assert client.get("/api/v1/feedback").json() == {"feedback": {REF: "down"}}


def test_invalid_verdict_ignored(client):
    r = client.post("/api/v1/feedback", json={"ref": REF, "verdict": "meh"})
    assert r.json() == {"ref": REF, "verdict": None}
    assert client.get("/api/v1/feedback").json() == {"feedback": {}}


def test_summary_counts_by_source(client):
    client.post("/api/v1/feedback",
                json={"ref": "atmosphere:1:music:Claude", "verdict": "up", "source": "Claude"})
    client.post("/api/v1/feedback",
                json={"ref": "atmosphere:1:food:Claude", "verdict": "up", "source": "Claude"})
    client.post("/api/v1/feedback",
                json={"ref": "atmosphere:1:music:ChatGPT", "verdict": "down", "source": "ChatGPT"})
    summary = client.get("/api/v1/feedback/summary").json()["summary"]
    assert summary["Claude"] == {"up": 2, "down": 0}
    assert summary["ChatGPT"] == {"up": 0, "down": 1}
