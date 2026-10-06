"""Bounded output profiles; dimensions describe encoded frames, not source probes."""
import re


def scale_filter(width, height):
    # Evaluate on FFmpeg's actual decoded frame (including automatic rotation).
    # Even dimensions are required by yuv420p. SAR is retained, not flattened.
    return (f"scale=w='min(iw,{width})':h='min(ih,{height})':"
            "force_original_aspect_ratio=decrease:force_divisible_by=2")


def output_dimensions(log):
    """Read only the output video stream; never mistake source size for output."""
    output = log.decode('utf-8', errors='replace').partition('Output #0,')[2]
    for line in output.splitlines():
        if re.search(r'Stream #0:0(?:\[[^]]*\])?(?:\([^)]*\))?: Video:', line):
            match = re.search(r',\s*(\d+)x(\d+)(?:\s|,|\[)', line)
            if match:
                width, height = map(int, match.groups())
                if width >= 2 and height >= 2 and width % 2 == height % 2 == 0:
                    return width, height
    raise RuntimeError('无法确认转码输出尺寸')


def master_playlist(variants):
    rows = ['#EXTM3U']
    for variant in variants:
        rows.extend([f"#EXT-X-STREAM-INF:BANDWIDTH={variant['bandwidth']},"
                     f"RESOLUTION={variant['width']}x{variant['height']}",
                     f"{variant['profile']}/index.m3u8"])
    return '\n'.join(rows) + '\n'
