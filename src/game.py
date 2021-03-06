import contextlib
import asyncio
import telnetlib3
import logging

from src.connection import Connection
from src.handlers.login_handler import LoginHandler
import src.utils.vt100_codes as vt100

class Game(object):
  def __init__(self):
    logging.info('Intializing game...')
    self._connections = []
    self._loop = asyncio.get_event_loop()

  def total_connections(self):
    return len(self._connections)

  @contextlib.contextmanager
  def register_link(self, reader, writer):
    connection = Connection(reader, writer, notify_queue=asyncio.Queue())
    self._connections.append(connection)
    try:
      yield connection

    finally:
      self._connections.remove(connection)

  @asyncio.coroutine
  def main_loop(self, connection):
    from telnetlib3 import WONT, ECHO, SGA
    connection.set_iac(WONT, SGA)
    connection.set_echo(True)
    readline = asyncio.ensure_future(connection.readline())
    recv_msg = asyncio.ensure_future(connection.notify_queue.get())

    connection.enter_handler(LoginHandler(connection))

    wait_for = set([readline, recv_msg])
    try:
      while True:
        # client.writer.write('? ')
        # connection.current_handler().prompt()

        # await (1) client input or (2) system notification
        done, pending = yield from asyncio.wait(
          wait_for, return_when=asyncio.FIRST_COMPLETED)

        task = done.pop()
        wait_for.remove(task)
        if task == readline:
          # (1) client input
          cmd = (task.result()
               .rstrip())

          # connection.echo(cmd)
          connection.send(vt100.home)
          connection.handler().handle(cmd)

          # await next,
          readline = asyncio.ensure_future(connection.readline())
          wait_for.add(readline)

        else:
          # (2) system notification
          msg = task.result()

          # await next,
          recv_msg = asyncio.ensure_future(connection.notify_queue.get())
          wait_for.add(recv_msg)

          # show and display prompt,
          # client.current_state().prompt(msg)

        if connection.handler() == None:
          if connection in self._connections:
            connection.close()
            break
    finally:
      for task in wait_for:
        task.cancel()

