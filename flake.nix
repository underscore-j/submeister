{
  inputs = {
    utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { nixpkgs, utils, ...}:
    utils.lib.eachDefaultSystem (system:
      let pkgs = import nixpkgs { inherit system; };
      in {
        packages.submeister = pkgs.python3Packages.buildPythonApplication {
          pname = "submeister";
          version = "dev";

          src = ./.;

          dependencies = with pkgs; [
            (python3.withPackages (ps: with ps; [
              discordpy
              pynacl
              python-dotenv
              requests
            ]))
          ];

          pyproject = true;
          build-system = [ pkgs.python3Packages.setuptools ];

        };

        devShell = pkgs.mkShellNoCC {
          buildInputs = with pkgs; [
            (python3.withPackages (ps: with ps; [
              discordpy
              pynacl
              python-dotenv
              requests
            ]))
          ];
        };
      });
}
