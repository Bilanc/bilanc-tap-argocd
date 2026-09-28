"""tap-argocd: Argo CD applications and sync history."""
from singer import get_logger, utils

from tap_argocd.discover import discover
from tap_argocd.sync import sync

REQUIRED_CONFIG_KEYS = ["base_url", "token", "start_date"]
LOGGER = get_logger()


@utils.handle_top_exception(LOGGER)
def main():
    args = utils.parse_args(REQUIRED_CONFIG_KEYS)
    if args.discover:
        discover(args.config).dump()
    else:
        sync(args.config, args.state, args.catalog or discover(args.config))


if __name__ == "__main__":
    main()
