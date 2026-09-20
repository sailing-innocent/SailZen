# -*- coding: utf-8 -*-
# @file cli.py
# @brief SailZen CLI root command group (click)
# @author sailing-innocent
# @date 2026-09-20
# @version 2.0
# ---------------------------------

"""
SailZen CLI 根命令组

sailzen --version
sailzen finance / health / notes / note / rhythm / vault
"""

import click

from sailzen_cli import __version__


@click.group()
@click.version_option(version=__version__, prog_name="sailzen")
def cli():
    """SailZen CLI - 个人知识管理与生产力工具命令行端。"""


# 子命令组注册
from sailzen_cli.commands.finance_client import finance as finance_group
from sailzen_cli.commands.health_client import health as health_group
from sailzen_cli.commands.note_client import note as note_group
from sailzen_cli.commands.notes_client import notes as notes_group
from sailzen_cli.commands.rhythm_client import rhythm as rhythm_group
from sailzen_cli.commands.vault_client import vault as vault_group

cli.add_command(finance_group)
cli.add_command(health_group)
cli.add_command(note_group)
cli.add_command(notes_group)
cli.add_command(rhythm_group)
cli.add_command(vault_group)


def main():
    cli()


if __name__ == "__main__":
    main()
