class Simmer < Formula
  desc "Stream iOS Simulator and Android Emulator to any browser with touch, keyboard, and terminal"
  homepage "https://github.com/joshdholtz/simmer"
  license "MIT"

  on_arm do
    url "https://github.com/joshdholtz/simmer/releases/download/v0.2.0/simmer-v0.2.0-arm64.tar.gz"
    sha256 "" # filled in by release workflow
  end

  on_intel do
    url "https://github.com/joshdholtz/simmer/releases/download/v0.2.0/simmer-v0.2.0-x86_64.tar.gz"
    sha256 "" # filled in by release workflow
  end

  def install
    bin.install "simmer"
    bin.install "rotate_sim"
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
