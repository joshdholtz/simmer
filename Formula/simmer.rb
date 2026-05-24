class Simmer < Formula
  include Language::Python::Virtualenv

  desc "Stream iOS Simulator to your browser with touch, keyboard, and terminal"
  homepage "https://github.com/joshdholtz/simmer"
  url "https://github.com/joshdholtz/simmer/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "" # fill in after tagging first release
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
    url ""
    sha256 ""
  end

  resource "pyobjc-framework-Cocoa" do
    url ""
    sha256 ""
  end

  resource "pyobjc-framework-Quartz" do
    url ""
    sha256 ""
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
