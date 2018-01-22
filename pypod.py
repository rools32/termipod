#!/usr/bin/python
from itemlist import ItemList
from ui import start as uiStart

itemList = ItemList('pypod.db')

uiStart(itemList)
