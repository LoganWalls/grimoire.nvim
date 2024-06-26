{
  description = "Your customizable AI coding assistant";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };
  outputs = {nixpkgs, ...}: let
    inherit (nixpkgs) lib;
    withSystem = f:
      lib.fold lib.recursiveUpdate {}
      (map f ["x86_64-linux" "x86_64-darwin" "aarch64-linux" "aarch64-darwin"]);
  in
    withSystem (
      system: let
        pkgs = nixpkgs.legacyPackages.${system};
        inherit (pkgs) lib stdenv;
        # Use impure cc on Darwin so that python packages build correctly
        mkShell =
          if stdenv.isLinux
          then pkgs.mkShell
          else pkgs.mkShell.override {stdenv = pkgs.stdenvNoCC;};
      in {
        devShells.${system}.default =
          mkShell
          {
            packages = with pkgs; [
              python311
              uv
            ];
            # Build llama-cpp with Metal support on Darwin
            CMAKE_ARGS = lib.optional (system == "aarch64-darwin") "-DLLAMA_METAL=on";
            LD_LIBRARY_PATH = lib.optional stdenv.isLinux (pkgs.lib.makeLibraryPath [
              pkgs.stdenv.cc.cc
            ]);

            # Use ipdb
            PYTHONBREAKPOINT = "ipdb.set_trace";

            shellHook = ''
              if [ ! -d .venv ]; then
                uv venv
                uv pip install -e '.[dev]'
              fi
              source .venv/bin/activate
            '';
          };
      }
    );
}
