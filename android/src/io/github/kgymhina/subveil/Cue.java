package io.github.kgymhina.subveil;

final class Cue {
    final long startMs;
    final long endMs;
    final String text;

    Cue(long startMs, long endMs, String text) {
        this.startMs = startMs;
        this.endMs = endMs;
        this.text = text;
    }
}
