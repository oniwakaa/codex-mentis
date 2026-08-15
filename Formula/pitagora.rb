class Pitagora < Formula
  desc "AI-powered math & physics tutoring CLI with multi-agent reasoning"
  homepage "https://github.com/oniwakaa/codex-mentis"
  url "https://files.pythonhosted.org/packages/source/p/pitagora/pitagora-1.0.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "Pitagora", shell_output("#{bin}/pitagora --help")
  end
end
