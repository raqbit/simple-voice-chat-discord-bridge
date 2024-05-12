import asyncio

from twisted.internet import asyncioreactor

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

asyncioreactor.install(loop)
