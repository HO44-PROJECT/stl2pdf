import numpy as np
from stl import mesh
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, A3, LETTER, LEGAL
from reportlab.lib.units import mm
import datetime
import os
import argparse
from scipy.spatial import ConvexHull
from typing import List, Tuple, Optional

# Version du script
VERSION = "1.0"

# Supported paper sizes
PAPER_SIZES = {
    'A4': A4,
    'A3': A3,
    'Letter': LETTER,
    'Legal': LEGAL
}

def read_stl_shadow(stl_file: str, footprint_type: str = 'full') -> np.ndarray:
    """Read the STL file and project facets onto the z=0 plane to obtain the footprint.

    Args:
        stl_file (str): Path to the input STL file.
        footprint_type (str): Type of footprint ('full' for all facets, 'ground' for facets touching z=0).

    Returns:
        np.ndarray: Array of 2D facets (x, y coordinates) representing the footprint.

    Raises:
        ValueError: If footprint_type is invalid.
    """
    if footprint_type not in ['full', 'ground']:
        raise ValueError("footprint_type must be 'full' or 'ground'")
    
    # Load the STL file using the mesh library
    stl_mesh = mesh.Mesh.from_file(stl_file)
    shadow_facets = []
    
    # Process facets based on footprint type
    for facet in stl_mesh.vectors:
        if footprint_type == 'ground':
            # Check if any vertex of the facet has z-coordinate close to 0 (within 0.01 mm)
            z_coords = facet[:, 2]
            if any(abs(z) < 0.01 for z in z_coords):
                shadow_facets.append(facet[:, :2])  # Keep only x, y for ground-touching facets
        else:
            # For 'full', include all facets projected onto z=0
            shadow_facets.append(facet[:, :2])
    
    return np.array(shadow_facets)

def project_to_2d(facets: np.ndarray, scale: float = 1.0) -> np.ndarray:
    """Project facets to 2D (x, y) and apply scaling.

    Args:
        facets (np.ndarray): Array of facets with x, y coordinates.
        scale (float): Scaling factor to apply to the facets (default: 1.0).

    Returns:
        np.ndarray: Scaled array of facets.
    """
    # Apply scaling to x, y coordinates
    return facets * scale

def get_bounding_box(facets: np.ndarray) -> Tuple[float, float, float, float]:
    """Calculate the bounding box of the facets.

    Args:
        facets (np.ndarray): Array of facets with x, y coordinates.

    Returns:
        Tuple[float, float, float, float]: Minimum and maximum x, y coordinates (min_x, min_y, max_x, max_y).

    Raises:
        ValueError: If the facets array is empty or contains no points.
    """
    if len(facets) == 0:
        raise ValueError("No facets provided to calculate bounding box")
    
    # Reshape facets to a 2D array of points for bounding box calculation
    facets_array = np.array(facets)
    if facets_array.size == 0:
        raise ValueError("Facets array is empty")
    
    all_points = facets_array.reshape(-1, 2)
    min_x, min_y = np.min(all_points, axis=0)
    max_x, max_y = np.max(all_points, axis=0)
    return min_x, min_y, max_x, max_y

def rotate_facets(facets: np.ndarray, angle_deg: float) -> np.ndarray:
    """Apply a rotation to the facets around the origin (in degrees).

    Args:
        facets (np.ndarray): Array of facets to rotate.
        angle_deg (float): Rotation angle in degrees.

    Returns:
        np.ndarray: Rotated facets.
    """
    # Convert angle to radians and create rotation matrix
    angle_rad = np.radians(angle_deg)
    rotation_matrix = np.array([
        [np.cos(angle_rad), -np.sin(angle_rad)],
        [np.sin(angle_rad), np.cos(angle_rad)]
    ])
    
    # Apply rotation to each facet
    rotated_facets = []
    for facet in facets:
        rotated_facet = np.dot(facet, rotation_matrix)
        rotated_facets.append(rotated_facet)
    return np.array(rotated_facets)

def find_optimal_rotation(facets: np.ndarray, page_width: float, page_height: float) -> float:
    """Find the rotation angle that aligns the principal axis vertically to optimize page usage.

    Args:
        facets (np.ndarray): Array of facets to analyze.
        page_width (float): Width of the page in mm (paper width - margins).
        page_height (float): Height of the page in mm (paper height - margins).

    Returns:
        float: Optimal rotation angle in degrees.
    """
    # Flatten facets to a 2D array of points for PCA
    all_points = np.array(facets).reshape(-1, 2)
    mean = np.mean(all_points, axis=0)
    centered_points = all_points - mean
    
    # Compute covariance matrix and principal axis using PCA
    cov_matrix = np.cov(centered_points.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
    principal_axis = eigenvectors[:, np.argmax(eigenvalues)]
    angle_rad = np.arctan2(principal_axis[1], principal_axis[0])
    angle_deg = np.degrees(angle_rad)
    
    # Target angle aligns the principal axis vertically (subtract 90°)
    target_angle = angle_deg - 90
    best_angle = target_angle
    min_area = float('inf')
    target_width, target_height = page_width - 20, page_height - 20
    
    # Test angles around the target to find the best fit within page dimensions
    for angle in np.arange(target_angle - 15, target_angle + 15, 1):
        rotated_facets = rotate_facets(facets, angle)
        min_x, min_y, max_x, max_y = get_bounding_box(rotated_facets)
        width = max_x - min_x
        height = max_y - min_y
        area = width * height
        
        if width <= target_width and height <= target_height:
            return angle
        if area < min_area:
            min_area = area
            best_angle = angle
    
    return best_angle

def calculate_area_and_perimeter(facets: np.ndarray, scale: float = 1.0) -> Tuple[float, float]:
    """Calculate the area and perimeter of the outer contour of the projection.

    Args:
        facets (np.ndarray): Array of facets.
        scale (float): Scaling factor to apply to area and perimeter (default: 1.0).

    Returns:
        Tuple[float, float]: Area in mm² and perimeter in mm, adjusted for scale.
    """
    # Calculate area by summing the areas of all triangles
    area = 0.0
    for facet in facets:
        v0, v1, v2 = facet
        v0_3d = np.append(v0, 0)
        v1_3d = np.append(v1, 0)
        v2_3d = np.append(v2, 0)
        area += 0.5 * abs(np.cross(v1_3d - v0_3d, v2_3d - v0_3d)[2])
    
    # Adjust area for scale (area scales with square of the factor)
    area *= scale * scale
    
    # Calculate perimeter using the convex hull of all points
    all_points = np.array(facets).reshape(-1, 2)
    hull = ConvexHull(all_points)
    hull_points = all_points[hull.vertices]
    perimeter = 0.0
    for i in range(len(hull_points)):
        p1 = hull_points[i]
        p2 = hull_points[(i + 1) % len(hull_points)]
        perimeter += np.sqrt(np.sum((p2 - p1) ** 2))
    
    # Adjust perimeter for scale
    perimeter *= scale
    
    return area, perimeter

def calculate_principal_angle(facets: np.ndarray) -> float:
    """Calculate the principal angle of the footprint in degrees using PCA.

    Args:
        facets (np.ndarray): Array of facets.

    Returns:
        float: Principal angle in degrees.
    """
    # Flatten facets to a 2D array of points
    all_points = np.array(facets).reshape(-1, 2)
    mean = np.mean(all_points, axis=0)
    centered_points = all_points - mean
    
    # Compute principal axis using PCA
    cov_matrix = np.cov(centered_points.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
    principal_axis = eigenvectors[:, np.argmax(eigenvalues)]
    angle_rad = np.arctan2(principal_axis[1], principal_axis[0])
    return np.degrees(angle_rad)

def split_to_pages(facets: np.ndarray, page_width: float, page_height: float) -> List[Tuple[np.ndarray, float, float]]:
    """Split the facets into pages at 1:1 scale (adjusted by scale factor).

    Args:
        facets (np.ndarray): Array of facets to split.
        page_width (float): Width of the paper in mm.
        page_height (float): Height of the paper in mm.

    Returns:
        List[Tuple[np.ndarray, float, float]]: List of tuples containing facets for each page and their offsets (x_offset, y_offset).
    """
    # Get the bounding box of the facets
    min_x, min_y, max_x, max_y = get_bounding_box(facets)
    width = max_x - min_x
    height = max_y - min_y
    
    pages = []
    x_start = min_x
    # Iterate over x and y to create pages
    while x_start < max_x:
        y_start = min_y
        while y_start < max_y:
            page_facets = []
            for facet in facets:
                # Check if the facet fits within the current page
                if (np.all(facet[:, 0] >= x_start) and np.all(facet[:, 0] <= x_start + page_width) and
                    np.all(facet[:, 1] >= y_start) and np.all(facet[:, 1] <= y_start + page_height)):
                    page_facets.append(facet - np.array([x_start, y_start]))
            if page_facets:
                pages.append((page_facets, x_start, y_start))
            y_start += page_height
        x_start += page_width
    return pages

def draw_grid(c: canvas.Canvas, page_width: float, page_height: float) -> None:
    """Draw a millimeter grid on the page.

    Args:
        c (canvas.Canvas): Reportlab canvas object for drawing.
        page_width (float): Width of the page in mm.
        page_height (float): Height of the page in mm.
    """
    # Set line style for the grid
    c.setLineWidth(0.2)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    
    # Draw horizontal lines every 10 mm
    for y in range(0, int(page_height) + 10, 10):
        c.line(0, y * mm, page_width * mm, y * mm)
    
    # Draw vertical lines every 10 mm
    for x in range(0, int(page_width) + 10, 10):
        c.line(x * mm, 0, x * mm, page_height * mm)
    
    # Add labels for scale
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0, 0, 0)
    for x in range(0, int(page_width) + 50, 50):
        c.drawString(x * mm, 2 * mm, f"{x} mm")
    for y in range(0, int(page_height) + 50, 50):
        c.drawString(2 * mm, y * mm, f"{y} mm")

def generate_pdf(facets: np.ndarray, output_pdf: str, stl_filename: str, paper_size: tuple, 
                 show_filename: bool = False, global_rotation: float = 0, creator: str = "Unknown Creator", 
                 title: str = "Untitled", scale: float = 1.0) -> None:
    """Generate a multi-page PDF with the centered footprint, grid, and metadata.

    Args:
        facets (np.ndarray): Array of 2D facets to draw.
        output_pdf (str): Path to the output PDF file.
        stl_filename (str): Name of the input STL file for metadata.
        paper_size (tuple): Tuple of (width, height) in points for the paper size.
        show_filename (bool): Whether to display the filename inside the footprint.
        global_rotation (float): Global rotation angle applied to the facets (in degrees).
        creator (str): Creator metadata to display in the PDF.
        title (str): Title metadata to display in the PDF.
        scale (float): Scaling factor applied to the footprint.
    """
    # Initialize the PDF canvas with specified paper size
    c = canvas.Canvas(output_pdf, pagesize=paper_size)
    page_width, page_height = paper_size[0] / mm, paper_size[1] / mm
    
    # Split facets into pages
    pages = split_to_pages(facets, page_width, page_height)
    
    # Calculate bounding box, area, and perimeter for metadata
    min_x, min_y, max_x, max_y = get_bounding_box(facets)
    width = max_x - min_x
    height = max_y - min_y
    area, perimeter = calculate_area_and_perimeter(facets, scale)
    
    # Define metadata strings
    subtitle = f"Footprint - {os.path.basename(stl_filename)}"
    source = f"Source: {os.path.basename(stl_filename)}"
    dimensions = f"Dimensions: {width:.2f} × {height:.2f} mm"
    area_str = f"Area: {area:.2f} mm²"
    perimeter_str = f"Perimeter: {perimeter:.2f} mm"
    scale_str = f"Scale: 1:{1/scale:.2f}" if scale != 1.0 else "Scale: 1:1 (Real scale)"
    generation_date = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    
    # Process each page
    for page_num, (page_facets, x_offset, y_offset) in enumerate(pages, 1):
        # Calculate offsets to center the footprint on the page
        min_x, min_y, max_x, max_y = get_bounding_box(page_facets)
        shape_width = max_x - min_x
        shape_height = max_y - min_y
        offset_x = (page_width - shape_width) / 2 - min_x
        offset_y = (page_height - shape_height) / 2 - min_y
        
        # Draw the grid
        draw_grid(c, page_width, page_height)
        
        # Draw metadata
        c.setFont("Helvetica-Bold", 12)
        c.setFillColorRGB(0, 0, 0)
        y_pos = paper_size[1] - 10 * mm
        c.drawString(10 * mm, y_pos, title)
        y_pos -= 5 * mm
        c.setFont("Helvetica", 10)
        c.drawString(10 * mm, y_pos, creator)
        y_pos -= 5 * mm
        c.drawString(10 * mm, y_pos, subtitle)
        y_pos -= 5 * mm
        c.drawString(10 * mm, y_pos, source)
        y_pos -= 5 * mm
        c.drawString(10 * mm, y_pos, dimensions)
        y_pos -= 5 * mm
        c.drawString(10 * mm, y_pos, area_str)
        y_pos -= 5 * mm
        c.drawString(10 * mm, y_pos, perimeter_str)
        y_pos -= 5 * mm
        c.drawString(10 * mm, y_pos, scale_str)
        y_pos -= 5 * mm
        c.drawString(10 * mm, y_pos, f"Generated on: {generation_date}")
        y_pos -= 5 * mm
        c.drawString(10 * mm, y_pos, f"Page: {page_num}")
        
        # Draw the footprint
        c.setLineWidth(0.1)
        c.setStrokeColorRGB(0, 0, 0)
        for facet in page_facets:
            translated_facet = facet + np.array([offset_x, offset_y])
            c.lines([(pt[0] * mm, pt[1] * mm, translated_facet[(i + 1) % 3][0] * mm, translated_facet[(i + 1) % 3][1] * mm)
                     for i, pt in enumerate(translated_facet)])
        
        # Optionally draw the filename inside the footprint
        if show_filename:
            c.saveState()
            c.setFont("Helvetica", 8)
            c.setFillColorRGB(0, 0, 0)
            center_x = (page_width / 2) * mm
            center_y = (page_height / 2) * mm
            angle = calculate_principal_angle(page_facets) + global_rotation
            c.translate(center_x, center_y)
            c.rotate(angle)
            c.drawCentredString(0, 0, os.path.basename(stl_filename))
            c.restoreState()
        
        c.showPage()
    
    # Save the PDF
    c.save()

def print_usage_and_exit(parser: argparse.ArgumentParser, error_message: str, exit_code: int = 1) -> None:
    """Print the error message followed by the usage information and exit.

    Args:
        parser (argparse.ArgumentParser): The argument parser to display usage.
        error_message (str): The error message to display.
        exit_code (int): Exit code for the program (default: 1).
    """
    print(f"Error: {error_message}")
    print("\nUsage information:")
    parser.print_help()
    exit(exit_code)

def main(stl_files: Optional[List[str]] = None, show_filename: bool = False, destination_dir: Optional[str] = None, 
         source_dir: Optional[str] = None, creator: str = "Unknown Creator", title: str = "Untitled",
         paper_size: str = "A4", scale: float = 1.0, footprint_type: str = "full") -> None:
    """Main function to process STL files and generate PDFs.

    Args:
        stl_files (Optional[List[str]]): List of paths to STL files to process.
        show_filename (bool): Whether to display the filename inside the footprint.
        destination_dir (Optional[str]): Directory where PDFs are saved, preserving subdirectory structure.
        source_dir (Optional[str]): Directory for recursive search of STL files.
        creator (str): Creator metadata to display in the PDF.
        title (str): Title metadata to display in the PDF.
        paper_size (str): Paper size for the PDF ('A4', 'A3', 'Letter', 'Legal').
        scale (float): Scaling factor for the footprint (default: 1.0 for real scale).
        footprint_type (str): Type of footprint ('full' or 'ground').

    Raises:
        ValueError: If paper_size or footprint_type is invalid.
    """
    # Initialize parser for error handling
    parser = argparse.ArgumentParser(
        description=f"stl2pdf v{VERSION}: Convert one or more STL files or all STL files in a directory to PDF with the 2D footprint projection."
    )
    parser.add_argument("stl_files", nargs='*', help="Paths to the input STL files (optional if --source-dir is used)")
    parser.add_argument("--show-filename", action="store_true", help="Display the filename inside the footprint shape")
    parser.add_argument("--destination-dir", help="Destination directory for the generated PDF files")
    parser.add_argument("--source-dir", help="Source directory for recursive search of STL files")
    parser.add_argument("--creator", default="Unknown Creator", 
                       help="Creator metadata to display in the PDF (default: 'Unknown Creator')")
    parser.add_argument("--title", default="Untitled", 
                       help="Title metadata to display in the PDF (default: 'Untitled')")
    parser.add_argument("--paper-size", default="A4", 
                       help="Paper size for the PDF (A4, A3, Letter, Legal; default: A4)")
    parser.add_argument("--scale", type=float, default=1.0, 
                       help="Scaling factor for the footprint (default: 1.0 for real scale)")
    parser.add_argument("--footprint-type", default="full", 
                       help="Type of footprint: 'full' for all facets, 'ground' for facets touching z=0 (default: 'full')")

    # Validate paper size
    if paper_size not in PAPER_SIZES:
        print_usage_and_exit(parser, f"Invalid paper size '{paper_size}'. Supported sizes: {', '.join(PAPER_SIZES.keys())}")
    
    # Validate scale
    if scale <= 0:
        print_usage_and_exit(parser, "Scale must be a positive number")
    
    # Validate footprint type
    if footprint_type not in ['full', 'ground']:
        print_usage_and_exit(parser, "footprint_type must be 'full' or 'ground'")
    
    # Get paper dimensions
    paper_dimensions = PAPER_SIZES[paper_size]
    page_width, page_height = paper_dimensions[0] / mm, paper_dimensions[1] / mm
    
    if source_dir:
        # Handle recursive processing of STL files in source_dir
        source_dir = os.path.realpath(source_dir)  # Resolve symbolic links
        if not os.path.isdir(source_dir):
            print_usage_and_exit(parser, f"Source directory '{source_dir}' does not exist or is not a directory.")
        
        # Count STL files for diagnostic purposes
        stl_files_found = 0
        for root, _, files in os.walk(source_dir):
            for file in files:
                if file.lower().endswith('.stl'):
                    stl_files_found += 1
                    stl_path = os.path.join(root, file)
                    # Generate output PDF path
                    base_name = os.path.splitext(file)[0] + ".pdf"
                    if destination_dir:
                        destination_dir = os.path.realpath(destination_dir)  # Resolve symbolic links
                        relative_path = os.path.relpath(root, start=source_dir)
                        output_dir = os.path.join(destination_dir, relative_path)
                        os.makedirs(output_dir, exist_ok=True)
                        output_pdf = os.path.join(output_dir, base_name)
                    else:
                        output_pdf = os.path.join(root, base_name)
                    
                    print(f"Processing {stl_path}...")
                    try:
                        # Process the STL file
                        shadow_facets = read_stl_shadow(stl_path, footprint_type)
                        if len(shadow_facets) == 0:
                            print(f"No facets found in {stl_path}.")
                            continue
                        
                        optimal_angle = find_optimal_rotation(shadow_facets, page_width, page_height)
                        rotated_facets = rotate_facets(shadow_facets, optimal_angle)
                        facets_2d = project_to_2d(rotated_facets, scale)
                        generate_pdf(facets_2d, output_pdf, stl_path, paper_dimensions, show_filename, 
                                    optimal_angle, creator, title, scale)
                        min_x, min_y, max_x, max_y = get_bounding_box(facets_2d)
                        print(f"PDF generated: {output_pdf} (optimal rotation: {optimal_angle:.2f}°)")
                        print(f"Dimensions after rotation and scaling: {(max_x - min_x):.2f} × {(max_y - min_y):.2f} mm")
                    except Exception as e:
                        print_usage_and_exit(parser, f"Error processing {stl_path}: {e}")
        
        if stl_files_found == 0:
            print_usage_and_exit(parser, f"No STL files found in source directory '{source_dir}'.")
    
    elif stl_files:
        # Handle processing of multiple specified STL files
        for stl_file in stl_files:
            stl_file = os.path.realpath(stl_file)  # Resolve symbolic links
            if not os.path.isfile(stl_file):
                print_usage_and_exit(parser, f"STL file '{stl_file}' does not exist or is not a file.")
            
            base_name = os.path.splitext(os.path.basename(stl_file))[0] + ".pdf"
            if destination_dir:
                destination_dir = os.path.realpath(destination_dir)  # Resolve symbolic links
                relative_path = os.path.relpath(os.path.dirname(stl_file), start=os.path.dirname(os.path.abspath(stl_file)))
                output_dir = os.path.join(destination_dir, relative_path)
                os.makedirs(output_dir, exist_ok=True)
                output_pdf = os.path.join(output_dir, base_name)
            else:
                output_pdf = os.path.splitext(stl_file)[0] + ".pdf"
            
            print(f"Processing {stl_file}...")
            try:
                shadow_facets = read_stl_shadow(stl_file, footprint_type)
                if len(shadow_facets) == 0:
                    print(f"No facets found in {stl_file}.")
                    continue
                
                optimal_angle = find_optimal_rotation(shadow_facets, page_width, page_height)
                rotated_facets = rotate_facets(shadow_facets, optimal_angle)
                facets_2d = project_to_2d(rotated_facets, scale)
                generate_pdf(facets_2d, output_pdf, stl_file, paper_dimensions, show_filename, 
                             optimal_angle, creator, title, scale)
                min_x, min_y, max_x, max_y = get_bounding_box(facets_2d)
                print(f"PDF generated: {output_pdf} (optimal rotation: {optimal_angle:.2f}°)")
                print(f"Dimensions after rotation and scaling: {(max_x - min_x):.2f} × {(max_y - min_y):.2f} mm")
            except Exception as e:
                print_usage_and_exit(parser, f"Error processing {stl_file}: {e}")
    else:
        print_usage_and_exit(parser, "Please specify one or more STL files or a source directory with --source-dir.")

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description=f"stl2pdf v{VERSION}: Convert one or more STL files or all STL files in a directory to PDF with the 2D footprint projection."
    )
    parser.add_argument("stl_files", nargs='*', help="Paths to the input STL files (optional if --source-dir is used)")
    parser.add_argument("--show-filename", action="store_true", help="Display the filename inside the footprint shape")
    parser.add_argument("--destination-dir", help="Destination directory for the generated PDF files")
    parser.add_argument("--source-dir", help="Source directory for recursive search of STL files")
    parser.add_argument("--creator", default="Unknown Creator", 
                       help="Creator metadata to display in the PDF (default: 'Unknown Creator')")
    parser.add_argument("--title", default="Untitled", 
                       help="Title metadata to display in the PDF (default: 'Untitled')")
    parser.add_argument("--paper-size", default="A4", 
                       help="Paper size for the PDF (A4, A3, Letter, Legal; default: A4)")
    parser.add_argument("--scale", type=float, default=1.0, 
                       help="Scaling factor for the footprint (default: 1.0 for real scale)")
    parser.add_argument("--footprint-type", default="full", 
                       help="Type of footprint: 'full' for all facets, 'ground' for facets touching z=0 (default: 'full')")
    
    try:
        args = parser.parse_args()
    except SystemExit:
        print_usage_and_exit(parser, "Invalid command-line arguments.")
    
    if args.source_dir and args.stl_files:
        print("Warning: --source-dir is specified, the stl_files argument will be ignored.")
    
    # Run the main function with parsed arguments
    main(stl_files=args.stl_files, show_filename=args.show_filename, 
         destination_dir=args.destination_dir, source_dir=args.source_dir,
         creator=args.creator, title=args.title, paper_size=args.paper_size,
         scale=args.scale, footprint_type=args.footprint_type)