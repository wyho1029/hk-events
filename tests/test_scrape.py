import scrape


def make(id="a", title="活動", category="休閒", start="2099-01-01",
         end="2099-01-02"):
    return {"id": id, "title": title, "category": category, "start": start,
            "end": end, "venue": "", "url": "https://x", "source": "test"}


def test_is_entertainment():
    assert scrape.is_entertainment("巨星世界巡迴演唱會 2026")
    assert scrape.is_entertainment("XXX Fan Meeting in Hong Kong")
    assert not scrape.is_entertainment("香港馬拉松 2027")


def test_categorize():
    assert scrape.categorize("香港國際七人欖球賽", "大型盛事") == "體育"
    assert scrape.categorize("夏日手作市集", "休閒") == "休閒"


def test_valid():
    assert scrape.valid(make())
    assert not scrape.valid(make(start="2026/01/01"))
    assert not scrape.valid(make(category="娛樂"))
    bad = make()
    del bad["title"]
    assert not scrape.valid(bad)


def test_merge_dedupes_filters_and_sorts():
    a = make(id="1", start="2099-02-01", end="2099-02-01")
    dup = make(id="1", title="重複")
    ent = make(id="2", title="巨星演唱會")
    past = make(id="3", start="2000-01-01", end="2000-01-02")
    b = make(id="4", start="2099-01-01", end="2099-01-05")
    out = scrape.merge([[a, dup, ent], [past, b]], today="2026-07-13")
    assert [e["id"] for e in out] == ["4", "1"]


def test_merge_upgrades_sport_category():
    out = scrape.merge([[make(id="s", title="全港羽毛球錦標賽")]],
                       today="2026-07-13")
    assert out[0]["category"] == "體育"


def test_find_new():
    events = [make(id="1"), make(id="2")]
    assert [e["id"] for e in scrape.find_new(events, {"1": "2099-01-02"})] \
        == ["2"]


def test_discord_payload_caps_at_20():
    events = [make(id=str(i), title=f"活動{i}") for i in range(25)]
    p = scrape.build_discord_payload(events)
    desc = p["embeds"][0]["description"]
    assert "25" in p["embeds"][0]["title"]
    assert "仲有 5 個" in desc
    assert len(desc) <= 4096


def test_discord_payload_trailer_survives_long_titles():
    events = [make(id=str(i), title="長" * 300) for i in range(25)]
    p = scrape.build_discord_payload(events)
    desc = p["embeds"][0]["description"]
    assert len(desc) <= 4096
    assert "仲有" in desc
    assert desc.endswith("上網站睇晒")
