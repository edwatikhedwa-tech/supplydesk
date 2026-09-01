"""Матрица источников для изолированного smoke-теста."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    slug: str
    name: str
    url: str
    expected_mode: str
    note: str


SOURCES = (
    Source("productcenter", "ProductCenter", "https://productcenter.ru/", "direct", "производители РФ"),
    Source("pulscen-biz", "Пульс цен (.biz)", "https://www.pulscen.biz/", "not_confirmed", "домен из исходного списка; проверить отличие от pulscen.ru"),
    Source("promportal", "PromPortal", "https://promportal.su/", "direct", "товары и магазины компаний"),
    Source("metaprom", "Metaprom", "https://metaprom.ru/", "direct", "промышленный каталог компаний"),
    Source("opt-union", "Opt-Union", "https://www.opt-union.ru/", "direct", "товары и каталог компаний"),
    Source("postavshiki", "Postavshiki.com", "https://postavshiki.com/", "direct", "открытые карточки и контакты заявлены сайтом"),
    Source("postavshikov", "Postavshikov.net", "https://postavshikov.net/", "partial", "поиск поставщиков; доступ контактов проверить"),
    Source("optomtovar", "OptomTovar", "https://www.optomtovar.ru/", "direct", "оптовики и производители"),
    Source("all-biz", "All.biz", "https://all.biz/ru", "direct", "товары компаний и связь с продавцом"),
    Source("supl", "Supl.biz", "https://supl.biz/", "partial", "каталог открыт; контакты могут быть закрыты тарифом/входом"),
    Source("firstprice", "FirstPrice", "https://www.firstprice.ru/", "partial", "поиск открыт; контакты после входа"),
    Source("catalogvn", "CatalogVN", "https://www.catalogvn.ru/", "fallback", "справочник организаций и товаров"),
    Source("orgpage", "OrgPage", "https://www.orgpage.ru/", "fallback", "телефонный справочник; слабая товарная релевантность"),
    Source("optnavigator", "Опт Навигатор", "https://optnavigator.ru/", "direct", "публичные профили и товары заявлены сайтом"),
    Source("tonzar", "Tonzar B2B", "https://tonzar.com/ru/", "structured", "публичный MCP: поиск товара и getSupplier"),
    Source("bazaoptovik", "БазаОптовик", "https://bazaoptovik.ru/", "direct", "оптовый каталог; контакты поставщиков заявлены открытыми"),
    Source("flagma", "Flagma", "https://flagma.ru/", "direct", "каталог объявлений компаний и товаров"),
    Source("bizorg", "BizOrg.su", "https://bizorg.su/", "direct", "товары компаний и поставщики"),
    Source("plant", "Plant.ru", "https://www.plant.ru/", "direct", "каталог заводов и производств"),
    Source("fabricators", "Fabricators.ru", "https://fabricators.ru/", "direct", "поиск прямых производителей"),
    Source("edinprom", "EdinProm", "https://edinprom.ru/", "direct", "промышленный справочник компаний"),
)


SOURCE_BY_ROOT = {source.url.split("//", 1)[1].split("/", 1)[0].removeprefix("www."): source for source in SOURCES}
