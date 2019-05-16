## Development Guidelines

1. Code should adhere to [PEP8](https://www.python.org/dev/peps/pep-0008/).

1. Write clear commit messages, don't write commit message such as 'fix aaa' or
   'update'. If it is a small change to previous unmerged commits, you should
   just fix the older commit instead of adding random commits to fix them.

1. For commit titles, add a label in front of it so people can understand right
   away what it is about. For example, if I just implement new lib in shared
   package, my commit message would be like this:
   ```
   pkg: add libA
   ```
   You can even have multiple layer of label to make it even clearer, for example:
   ```
   pkg: libA: fix typos
   ```

1. For commit descriptions, write a slightly more detailed message to what you
   did. For example:
   ```
   pkg: add libA

   libA provides self-defined arithmetic operations by default rounding up
   decimal to integer.
   ```
   The commit title usually describe what change you made, and the commit
   message description usually describe the detail of why the change is made.

1. Keep your commits clean, each commit should have clear purpose. Don't mix a
   lot of changes doing different stuff in the same commit.

1. Test your changes with proper testcases and pass at least one CI flow (ex:
   Travis in this repository)
