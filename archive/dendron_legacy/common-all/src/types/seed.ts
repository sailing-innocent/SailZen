export type SeedConfig = {
  id: string;
  name: string;
  publisher: string;
  license: string;
  root: string;
  description: string;
  repository: SeedRepository;
  contact?: SeedContact;
  /**
   * Url for seed
   */
  site?: SeedSite;
  assets?: SeedBrowserAssets;
};

export type SeedSite = {
  url: string;
  index?: string;
};

export type SeedRepository = {
  type: "git";
  url: string;
  contact?: SeedContact;
};

export type SeedContact = {
  name: string;
  email?: string;
  url?: string;
};

export enum SeedCommands {
  ADD = "add",
  INIT = "init",
  INFO = "info",
  REMOVE = "remove",
}

export type SeedBrowserAssets = {
  seedIcon?: string;
  publisherLogo?: string;
};

export type SeedRegistryDict = { [key: string]: SeedConfig | undefined };

export const SEED_REGISTRY: SeedRegistryDict = {
  "sail.sail-site": {
    id: "sail.sail-site",
    name: "sail-site",
    publisher: "sail",
    description:
      "The Sail Wiki. This contains the Sail user guide, from getting started to advanced features. This also has information for Sail developers.",
    license: "Creative Commons Attribution 4.0 International",
    root: "vault",
    repository: {
      type: "git",
      url: "https://github.com/sailhq/sail-site.git",
    },
    site: {
      url: "https://wiki.sail.so",
      index: "sail",
    },
    assets: {
      publisherLogo:
        "https://org-sail-public-assets.s3.amazonaws.com/images/tutorial-logo_small.png",
    },
  },
  "sail.handbook": {
    id: "sail.handbook",
    name: "handbook",
    publisher: "sail",
    description:
      "The Sail Company Handbook. Outlines Company Values and Principles.",
    license: "Creative Commons Attribution 4.0 International",
    root: "handbook",
    repository: {
      type: "git",
      url: "https://github.com/sailhq/handbook.git",
    },
    site: {
      url: "https://handbook.sail.so",
      index: "handbook",
    },
    assets: {
      publisherLogo:
        "https://org-sail-public-assets.s3.amazonaws.com/images/tutorial-logo_small.png",
    },
  },
  "sail.templates": {
    id: "sail.templates",
    name: "templates",
    publisher: "sail",
    description: "Templates that can be applied to your new Sail notes.",
    license: "Creative Commons Attribution 4.0 International",
    root: "templates",
    repository: {
      type: "git",
      url: "https://github.com/sailhq/templates.git",
    },
    assets: {
      publisherLogo:
        "https://org-sail-public-assets.s3.amazonaws.com/images/tutorial-logo_small.png",
    },
  },
  "sail.tldr": {
    id: "sail.tldr",
    name: "tldr",
    publisher: "sail",
    description: "Documentation for the most popular CLI tools.",
    license: "Creative Commons Attribution 4.0 International",
    root: "vault",
    repository: {
      type: "git",
      url: "https://github.com/kevinslin/seed-tldr.git",
    },
    site: {
      url: "https://tldr.sail.so",
      index: "cli",
    },
    assets: {
      publisherLogo:
        "https://org-sail-public-assets.s3.amazonaws.com/images/tutorial-logo_small.png",
    },
  },
  "sail.xkcd": {
    id: "sail.xkcd",
    name: "xkcd",
    publisher: "sail",
    description: "A complete collection of xkcd comics by Randall Monroe",
    license: "Creative Commons Attribution-NonCommercial 2.5 License",
    root: "vault",
    repository: {
      type: "git",
      url: "https://github.com/kevinslin/seed-xkcd.git",
    },
    site: {
      url: "https://xkcd.sail.so",
    },
    assets: {
      publisherLogo:
        "https://org-sail-public-assets.s3.amazonaws.com/images/tutorial-logo_small.png",
    },
  },
  "sail.aws": {
    id: "sail.aws",
    name: "aws",
    publisher: "sail",
    description: "Documentation on all things related to AWS.",
    license: "Multiple",
    root: "vault",
    repository: {
      type: "git",
      url: "https://github.com/sailhq/sail-aws-vault.git",
    },
    site: {
      url: "https://aws.sail.so",
    },
    assets: {
      publisherLogo:
        "https://org-sail-public-assets.s3.amazonaws.com/images/tutorial-logo_small.png",
    },
  },
};
