"""Run the local CRIS-GVIE MVP voice interaction loop."""

from gvie import RuntimeConfig, VoiceRuntime


if __name__ == "__main__":
    runtime = VoiceRuntime(config=RuntimeConfig())
    runtime.run()
