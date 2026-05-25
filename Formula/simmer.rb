class Simmer < Formula
  include Language::Python::Virtualenv

  desc "Stream iOS Simulator to your browser with touch, keyboard, and terminal"
  homepage "https://github.com/joshdholtz/simmer"
  url "https://github.com/joshdholtz/simmer/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "b4778b853a3ec1f3c03c7d6b2d16a2603710c5c6d2f0883aa47b9590b6d19b51"
  license "MIT"

  depends_on "python@3.12"
  depends_on xcode: :build

  # Compat mode (no Screen Recording permission needed):
  #   brew tap facebook/fb && brew install idb-companion

  # To regenerate resource blocks after bumping versions:
  #   brew update-python-resources Formula/simmer.rb
  resource "aiohttp" do
    url "https://files.pythonhosted.org/packages/source/a/aiohttp/aiohttp-3.9.5.tar.gz"
    sha256 "edea7d15772ceeb29db4aff55e482d4bcfb6ae160ce144f2682de02f6d693551"
  end

  resource "pyobjc-core" do
    url "https://files.pythonhosted.org/packages/b8/b6/d5612eb40be4fd5ef88c259339e6313f46ba67577a95d86c3470b951fce0/pyobjc_core-12.1.tar.gz"
    sha256 "2bb3903f5387f72422145e1466b3ac3f7f0ef2e9960afa9bcd8961c5cbf8bd21"
  end

  resource "pyobjc-framework-Cocoa" do
    url "https://files.pythonhosted.org/packages/02/a3/16ca9a15e77c061a9250afbae2eae26f2e1579eb8ca9462ae2d2c71e1169/pyobjc_framework_cocoa-12.1.tar.gz"
    sha256 "5556c87db95711b985d5efdaaf01c917ddd41d148b1e52a0c66b1a2e2c5c1640"
  end

  resource "pyobjc-framework-Quartz" do
    url "https://files.pythonhosted.org/packages/94/18/cc59f3d4355c9456fc945eae7fe8797003c4da99212dd531ad1b0de8a0c6/pyobjc_framework_quartz-12.1.tar.gz"
    sha256 "27f782f3513ac88ec9b6c82d9767eef95a5cf4175ce88a1e5a65875fee799608"
  end

  def install
    # Build the Swift helper that handles simulator rotation
    system "swiftc", "-O", "rotate_sim.swift", "-o", "#{bin}/rotate_sim"

    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      Fast mode (Quartz capture) requires macOS permissions:
        System Settings → Privacy & Security → Screen Recording → simmer
        System Settings → Privacy & Security → Accessibility → rotate_sim

      Compat mode works without permissions but needs idb:
        brew tap facebook/fb && brew install idb-companion
    EOS
  end

  test do
    system "#{bin}/simmer", "--help"
  end
end
