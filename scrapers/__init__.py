from scrapers import brandhk, lcsd, timable

FETCHERS = [
    (lcsd.SOURCE, lcsd.fetch),
    (timable.SOURCE, timable.fetch),
    (brandhk.SOURCE, brandhk.fetch),
]
