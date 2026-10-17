"""`python -m zibaldone.ui [--web] [--port N] [--route /voci]`."""

import argparse

from zibaldone.ui.app import run


def cli() -> None:
    parser = argparse.ArgumentParser(prog="python -m zibaldone.ui", description="Apre l'interfaccia grafica di ZibaldOne.")
    parser.add_argument("--web", action="store_true", help="apri nel browser invece che in una finestra")
    parser.add_argument("--port", type=int, default=0, help="porta del server web (0 = una libera)")
    parser.add_argument("--route", default=None, help="la pagina da aprire, per esempio /voci o /scrivi/sera")
    arguments = parser.parse_args()
    run(web=arguments.web, port=arguments.port, route=arguments.route)


if __name__ == "__main__":
    cli()
