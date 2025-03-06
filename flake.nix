{
  inputs = {
    utils.url = "github:numtide/flake-utils";
  };

  outputs = { nixpkgs, utils, ...}:
    utils.lib.eachDefaultSystem (system:
      let pkgs = import nixpkgs { inherit system; };
      in {
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
