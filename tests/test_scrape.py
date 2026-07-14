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
    assert scrape.categorize("古埃及文明大展", "大型盛事") == "展覽"
    assert scrape.categorize("經典粵語片修復放映", "休閒") == "電影活動"
    assert scrape.categorize("中樂團週年音樂會", "休閒") == "表演藝術"
    assert scrape.categorize("國際綜藝合家歡開幕", "休閒") == "親子"
    # 優先次序：親子電影應該歸電影活動（電影組排先）
    assert scrape.categorize("親子電影放映會", "休閒") == "電影活動"


def test_merge_keeps_image_field():
    e = make(id="img")
    e["image"] = "https://img.example.com/a.jpg"
    out = scrape.merge([[e]], today="2026-07-13")
    assert out[0]["image"] == "https://img.example.com/a.jpg"
    out2 = scrape.merge([[make(id="noimg")]], today="2026-07-13")
    assert out2[0]["image"] == ""


def test_is_featured():
    assert scrape.is_featured(make(category="大型盛事"))
    assert scrape.is_featured(make(title="世界劍擊錦標賽2026", category="體育"))
    assert scrape.is_featured(make(title="香港國際七人欖球賽", category="體育"))
    assert not scrape.is_featured(make(title="跆拳道班", category="體育"))
    assert not scrape.is_featured(make(category="休閒"))


def test_merge_sets_featured_flag():
    big = make(id="b", title="世界女排聯賽香港站", category="體育")
    small = make(id="s", title="太極班", category="休閒")
    out = {e["id"]: e for e in scrape.merge([[big, small]], today="2026-07-13")}
    assert out["b"]["featured"] is True
    assert out["s"]["featured"] is False


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


def test_merge_normalizes_schemeless_urls():
    e = make(id="u")
    e["url"] = "www.example.com/x"
    out = scrape.merge([[e]], today="2026-07-13")
    assert out[0]["url"] == "https://www.example.com/x"


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


def test_merge_keeps_cinema_category():
    e = make(id="c", title="反斗奇兵5", category="電影")
    e["source"] = "hkmovie6"
    out = scrape.merge([[e]], today="2026-07-14")
    assert out[0]["category"] == "電影"


def test_merge_cinema_title_with_keyword_not_downgraded():
    # 戲名含「電影」二字，但係 hkmovie6 來源，唔應該變「電影活動」
    e = make(id="c2", title="這部電影很好看", category="電影")
    e["source"] = "hkmovie6"
    out = scrape.merge([[e]], today="2026-07-14")
    assert out[0]["category"] == "電影"


def test_cinema_excluded_from_discord_push():
    # 院線電影唔推 Discord，其餘照推
    new = [make(id="film", category="電影"),
           make(id="show", category="表演藝術")]
    assert [e["id"] for e in scrape.discord_events(new)] == ["show"]
