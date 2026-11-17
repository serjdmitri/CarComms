# Contributing

This is a personal robotics project by Sergey Dmitriev.

If you find a bug or have a suggestion, feel free to open an issue. Pull requests are welcome for improvements to the navigation logic or V2V communication protocol.

## Running the checks

The coordination package needs only Python 3.9+ and no third-party packages:

```bash
python3 -m unittest discover -s tests -t .
```

If you change the protocol or a policy, also re-run `python3 -m carcomms experiment --out docs/results` and commit the updated tables; CI fails if `docs/results/` no longer matches what the code produces.
