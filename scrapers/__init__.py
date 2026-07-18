from scrapers import brandhk, lcsd, timable, wmoov

FETCHERS = [
    (lcsd.SOURCE, lcsd.fetch),
    (timable.SOURCE, timable.fetch),
    (brandhk.SOURCE, brandhk.fetch),
    (wmoov.SOURCE, wmoov.fetch),
]
