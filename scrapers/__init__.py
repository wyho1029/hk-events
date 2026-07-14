from scrapers import brandhk, hkmovie, lcsd, timable

FETCHERS = [
    (lcsd.SOURCE, lcsd.fetch),
    (timable.SOURCE, timable.fetch),
    (brandhk.SOURCE, brandhk.fetch),
    (hkmovie.SOURCE, hkmovie.fetch),
]
