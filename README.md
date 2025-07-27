**Version**: 1.0

# STL2PDF Generator

This Python script converts STL files into PDF documents, displaying the 2D footprint (projection onto the z=0 plane) of 3D models on customizable paper sizes at a specified scale. The footprint is optimally rotated to align its principal axis vertically, ensuring efficient use of page space. The script supports processing one or more STL files or recursively processing all STL files in a directory.

## Features
- **Footprint Projection**: Projects the STL model onto the z=0 plane to create a 2D footprint. Supports two modes:
  - `full`: Projects all facets (default).
  - `ground`: Projects only facets with at least one vertex at z=0 (within 0.01 mm tolerance).
- **Optimal Rotation**: Uses Principal Component Analysis (PCA) to rotate the footprint so its longest dimension aligns with the vertical axis of the page.
- **Multi-Page Support**: Splits large footprints across multiple pages if they exceed the page size (after scaling).
- **Customizable Paper Size**: Supports A4, A3, Letter, and Legal paper sizes (default: A4).
- **Scaling**: Allows scaling the footprint with a custom scale factor (default: 1.0 for real scale).
- **Metadata**: Includes customizable metadata in the PDF:
  - Title: Customizable via `--title` (default: "Untitled")
  - Creator: Customizable via `--creator` (default: "Unknown Creator")
  - Subtitle: "Footprint - <filename>"
  - Source: "Source: <filename>"
  - Dimensions: Width and height of the footprint in mm (after scaling)
  - Area: Calculated area in mm² (after scaling)
  - Perimeter: Calculated perimeter of the outer contour using `ConvexHull` (after scaling)
  - Scale: Displays "Scale: 1:X" where X is the inverse of the scale factor (e.g., 1:2 for `--scale 0.5`)
  - Generation date and page number
- **Grid**: Draws a millimeter grid on each page for scale reference.
- **Filename Display**: Optionally displays the STL filename inside the footprint, rotated to match the principal axis.
- **Multiple STL Files**: Processes multiple STL files specified as arguments or all STL files in a directory with `--source-dir`.
- **Custom Output Directory**: Saves PDFs to a specified directory with `--destination-dir`, preserving the subdirectory structure.
- **Error Handling**: Provides clear error messages for invalid files, empty STL files, invalid paper sizes, or inaccessible directories.

## Dependencies
- Python 3.6+
- Required Python packages:
  - `numpy`: For numerical computations
  - `pystl`: For reading STL files
  - `reportlab`: For generating PDF documents
  - `scipy`: For calculating the convex hull (perimeter)

Install the dependencies using pip:
```bash
pip install numpy pystl reportlab scipy
```

## Installation
1. Save the script as `stl2pdf.py`.
2. Ensure the required Python packages are installed (see Dependencies).
3. Place the script in a directory accessible from your terminal.

## Usage
Run the script from the command line with the following options:

### Command Line Options
- `stl_files` (optional): One or more paths to STL files to process. Ignored if `--source-dir` is specified.
- `--show-filename`: If provided, displays the STL filename inside the footprint shape, rotated to match the principal axis.
- `--destination-dir <path>`: Specifies the output directory for generated PDFs. Preserves the subdirectory structure relative to the input file or source directory.
- `--source-dir <path>`: Specifies a directory to recursively search for STL files. If used, all STL files in the directory and its subdirectories are processed, and `stl_files` is ignored.
- `--creator <string>`: Specifies the creator metadata for the PDF (default: "Unknown Creator").
- `--title <string>`: Specifies the title metadata for the PDF (default: "Untitled").
- `--paper-size <string>`: Specifies the paper size for the PDF (A4, A3, Letter, Legal; default: A4).
- `--scale <float>`: Specifies the scaling factor for the footprint (e.g., 0.5 for half size; default: 1.0 for real scale).
- `--footprint-type <string>`: Specifies the type of footprint: `full` for all facets, `ground` for facets touching z=0 (default: `full`).

### Examples
1. **Process a single STL file with default settings**:
   ```bash
   python stl2pdf.py model.stl
   ```
   - Generates `model.pdf` in the same directory as `model.stl` using A4 paper, scale 1:1, and full footprint.

2. **Process multiple STL files with ground footprint**:
   ```bash
   python stl2pdf.py "roadv3 - 100mm - 90°.stl" "roadv3 - 200mm - 60°.stl" "roadv3 - 300mm - 45°.stl" --footprint-type ground
   ```
   - Generates `roadv3 - 100mm - 90°.pdf`, `roadv3 - 200mm - 60°.pdf`, and `roadv3 - 300mm - 45°.pdf` with ground-touching facets only.

3. **Process multiple STL files with custom metadata, paper size, and scale**:
   ```bash
   python stl2pdf.py repa/repb/model1.stl repa/repb/model2.stl --destination-dir output --creator "Jane Smith" --title "My 3D Models" --paper-size A3 --scale 0.5
   ```
   - Generates `output/repa/repb/model1.pdf` and `output/repa/repb/model2.pdf` with "Creator: Jane Smith", "My 3D Models", A3 paper, and half scale (1:2).

4. **Process all STL files in a directory with ground footprint**:
   ```bash
   python stl2pdf.py --source-dir stl --destination-dir pdf --footprint-type ground
   ```
   - Recursively processes all `.stl` files in the `stl` directory, using only ground-touching facets.
   - Generates PDFs in `pdf/<relative_path>/<filename>.pdf`, preserving the subdirectory structure.

5. **Process all STL files with custom metadata, filename display, and Legal paper size**:
   ```bash
   python stl2pdf.py --source-dir stl --destination-dir pdf --show-filename --creator "John Doe" --title "Custom Project" --paper-size Legal --scale 2.0 --footprint-type full
   ```
   - Processes all STL files with full footprint, doubled scale (1:0.5), Legal paper size, and includes the filename inside each footprint.

### Notes
- If both `stl_files` and `--source-dir` are provided, the script ignores `stl_files` and processes all STL files in `--source-dir`.
- The script handles symbolic links by resolving them to their real paths.
- If no STL files are found in `--source-dir`, a message is displayed.
- Errors (e.g., invalid STL files, permission issues, invalid paper size, or invalid footprint type) are reported in the terminal without stopping the processing of other files.
- The `--scale` option affects the dimensions, area, and perimeter displayed in the PDF metadata.
- The `--footprint-type ground` option may result in no facets if the STL model has no vertices close to z=0.

## Output Format
Each generated PDF contains:
- A 2D footprint of the STL model (full or ground-touching facets), optimally rotated to fit vertically on the specified paper size with 10 mm margins.
- A millimeter grid for scale reference.
- Metadata including customizable title, creator, dimensions, area, perimeter, scale (e.g., "Scale: 1:2" for `--scale 0.5`), generation date, and page number.
- Optionally, the filename displayed inside the footprint if `--show-filename` is used.

## Example Output
For an STL file `repa/repb/roadv3 - 300mm - 45°.stl` with `--creator "Jane Smith"`, `--title "My 3D Models"`, `--paper-size A3`, `--scale 0.5`, and `--footprint-type ground`:
- Terminal output:
  ```
  Processing repa/repb/roadv3 - 300mm - 45°.stl...
  PDF generated: pdf/repa/repb/roadv3 - 300mm - 45°.pdf (optimal rotation: X.XX°)
  Dimensions after rotation and scaling: WIDTH × HEIGHT mm
  ```
- PDF content:
  - Title: "My 3D Models"
  - Creator: "Creator: Jane Smith"
  - Footprint projection (ground-touching facets only) with grid
  - Metadata with dimensions, area, perimeter (adjusted for scale 0.5), and "Scale: 1:2"
  - Paper size: A3 (297 × 420 mm)

## Troubleshooting
- **No PDFs generated**: Ensure the STL files are valid and accessible. Check if `--source-dir` points to a directory containing `.stl` files. For `--footprint-type ground`, ensure the STL has vertices at z=0.
- **Permission errors**: Verify that you have read access to the STL files and write access to the destination directory.
- **Invalid paper size**: Use one of A4, A3, Letter, or Legal for `--paper-size`.
- **Invalid scale**: Ensure `--scale` is a positive number (e.g., 0.5 for half size, 2.0 for double size).
- **Large footprints**: If a footprint exceeds the paper size, it is split across multiple pages. Adjust `--scale` to fit larger models.
- **No ground facets**: If `--footprint-type ground` produces an empty PDF, the STL may have no vertices near z=0.
- **Multiple STL files error**: Ensure file paths are correctly quoted if they contain spaces or special characters.

For further assistance or feature requests, submit an issue or contact the script creator.