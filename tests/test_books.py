import books


def mk(title, rank=1):
    return {"rank": rank, "title": title, "author": "作者",
            "price": "NT$300", "url": "https://x", "image": "https://i"}


def test_build_excludes_manga():
    total = [mk("臺灣漫遊錄", 1), mk("鬼滅之刃 20 (特裝版)", 2),
             mk("槓桿ETF投資法", 3)]
    manga = [mk("鬼滅之刃 20 (特裝版)", 1)]
    out = books.build(total, manga)
    titles = [b["title"] for b in out]
    assert "鬼滅之刃 20 (特裝版)" not in titles
    assert titles == ["臺灣漫遊錄", "槓桿ETF投資法"]
    assert [b["rank"] for b in out] == [1, 2]  # 剔走後重新連續編號


def test_build_excludes_language_exam_books():
    total = [mk("臺灣漫遊錄", 1),
             mk("全新！新制多益 TOEIC 單字大全", 2),
             mk("IELTS 雅思聽力題庫", 3),
             mk("抄寫英語的奇蹟：1天10分鐘", 4),
             mk("大家的日語會話", 5),
             mk("槓桿ETF投資法", 6)]
    out = books.build(total, [])
    titles = [b["title"] for b in out]
    assert titles == ["臺灣漫遊錄", "槓桿ETF投資法"]
    assert [b["rank"] for b in out] == [1, 2]


def test_build_caps_top_n():
    total = [mk(f"書{i}", i) for i in range(30)]
    out = books.build(total, [], top_n=20)
    assert len(out) == 20
    assert [b["rank"] for b in out] == list(range(1, 21))


def test_norm_title_ignores_punctuation():
    # 同一本書兩榜寫法標點差異，要視為同書
    assert books._norm_title("鬼滅之刃 20（特裝版）") \
        == books._norm_title("鬼滅之刃20(特裝版)")


def test_parse_list_extracts_fields():
    html = """
    <ul><li class="item">
      <img class="cover" data-original="https://im.book/cover.jpg">
      <div class="type02_bd-a"><h4>
        <a href="https://www.books.com.tw/products/0010852315?loc=P_1">臺灣漫遊錄</a>
      </h4></div>
      <ul class="msg">
        <li>作者：<a href="/x">楊双子</a></li>
        <li class="price_a">優惠價：<strong><b>79</b></strong>折<strong><b>300</b></strong>元</li>
      </ul>
    </li></ul>
    """
    out = books.parse_list(html)
    assert len(out) == 1
    b = out[0]
    assert b["title"] == "臺灣漫遊錄"
    assert b["author"] == "楊双子"
    assert b["price"] == "NT$300"
    assert b["url"] == "https://www.books.com.tw/products/0010852315"  # 去 query
    assert b["image"] == "https://im.book/cover.jpg"
    assert b["rank"] == 1
