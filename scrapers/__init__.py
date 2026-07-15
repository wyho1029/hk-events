from scrapers import brandhk, hkmovie, lcsd, timable, wmoov

FETCHERS = [
    (lcsd.SOURCE, lcsd.fetch),
    (timable.SOURCE, timable.fetch),
    (brandhk.SOURCE, brandhk.fetch),
    (hkmovie.SOURCE, hkmovie.fetch),
    (wmoov.SOURCE, wmoov.fetch),
]
