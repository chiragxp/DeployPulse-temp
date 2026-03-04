
import json
from datetime import datetime
import requests
import argparse
import re
import os
from pathlib import Path
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
from html.parser import HTMLParser
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
AI_ENDPOINT = os.getenv('AI_ENDPOINT')


def parse_html_to_text(html_string):
    """Parse HTML string and convert to reportlab-compatible format with color mapping
    
    Removes escaped quotes from style attributes (e.g., \\\" becomes \") before parsing
    """
    # Unescape HTML quotes that were escaped in JSON response
    # Convert \" to " and \' to ' for proper HTML parsing
    html_string = html_string.replace('\\"', '"').replace("\\'", "'")
    
    class HTMLExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text_parts = []
            self.current_styles = {'bold': False, 'color': None}
            self.in_span_with_color = False
            
        def handle_starttag(self, tag, attrs):
            attrs_dict = dict(attrs)
            if tag == 'strong':
                self.current_styles['bold'] = True
            elif tag == 'span' and 'style' in attrs_dict:
                style = attrs_dict['style']
                if 'darkred' in style:
                    self.text_parts.append('<font color="red">')
                    self.in_span_with_color = True
                elif 'darkgreen' in style:
                    self.text_parts.append('<font color="green">')
                    self.in_span_with_color = True
        
        def handle_endtag(self, tag):
            if tag == 'strong':
                self.current_styles['bold'] = False
            elif tag == 'span' and self.in_span_with_color:
                self.text_parts.append('</font>')
                self.in_span_with_color = False
        
        def handle_data(self, data):
            if data.strip():
                if self.current_styles['bold']:
                    self.text_parts.append(f'<b>{data}</b>')
                else:
                    self.text_parts.append(data)
    
    extractor = HTMLExtractor()
    extractor.feed(html_string)
    return ''.join(extractor.text_parts)


def format_response_text(response_text):
    """Format HTML response text with metrics categories, titles, and color-coded spans"""
    styles = getSampleStyleSheet()

    # Create custom styles for headers
    h3_style = ParagraphStyle(
        'H3Style',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.black,
        spaceAfter=10,
        spaceBefore=10,
        fontName='Helvetica-Bold'
    )

    # Create custom styles for paragraphs (10pt)
    p_style = ParagraphStyle(
        'PStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.black,
        spaceAfter=8,
        spaceBefore=8,
        leading=14
    )

    story = []

    # Extract metrics categories from wrapper div
    category_pattern = r"<div class='metrics-category'>(.*?)</div>"
    categories = re.findall(category_pattern, response_text, re.DOTALL)

    for category in categories:
        # Extract h4 title with class 'metrics-title'
        h4_match = re.search(r"<h4[^>]*class='metrics-title'[^>]*>([^<]+)</h4>", category)
        if h4_match:
            title = h4_match.group(1).strip()
            story.append(Paragraph(title, h3_style))

        # Extract all paragraphs with class 'metrics-content'
        p_pattern = r"<p[^>]*class='metrics-content'[^>]*>(.*?)</p>"
        paragraphs = re.findall(p_pattern, category, re.DOTALL)
        
        for para_content in paragraphs:
            # Parse HTML within paragraph to convert spans and strong tags
            formatted_text = parse_html_to_text(para_content)
            
            if formatted_text.strip():
                try:
                    story.append(Paragraph(formatted_text, p_style))
                except (ValueError, AttributeError) as e:
                    # If parsing error, try without color tags
                    logger.warning(f"Failed to format paragraph text: {e}, attempting fallback")
                    plain_text = re.sub(r'<font[^>]*>|</font>', '', formatted_text)
                    story.append(Paragraph(plain_text, p_style))

    return story

def create_pdf_styles():
    """Create and return all PDF styling objects"""
    styles = getSampleStyleSheet()

    return {
        'title': ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=28,
            textColor=colors.black,
            spaceAfter=12,
            alignment=0
        ),
        'heading': ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.black,
            spaceAfter=12,
            spaceBefore=12
        ),
        'h3': ParagraphStyle(
            'H3Style',
            parent=styles['Heading1'],
            fontSize=14,
            textColor=colors.black,
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        ),
        'h4': ParagraphStyle(
            'H4Style',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.black,
            spaceAfter=10,
            spaceBefore=10,
            fontName='Helvetica-Bold'
        ),
        'p': ParagraphStyle(
            'PStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.black,
            spaceAfter=8,
            spaceBefore=8,
            leading=14
        ),
        'normal': styles['Normal']
    }

def load_json_file(filename):
    """Load and parse JSON file with error handling

    Args:
        filename: Path to JSON file to load

    Returns:
        dict: Parsed JSON data

    Raises:
        FileNotFoundError: If file does not exist
        json.JSONDecodeError: If file is not valid JSON
        IOError: If IO error occurs while reading
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"File not found: {filename}")

    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in file {filename}: Line {e.lineno}, Column {e.colno}: {e.msg}")
        raise
    except IOError as e:
        logger.error(f"IO error reading file {filename}: {e}")
        raise

def generate_comparison_charts(comparison_data, output_dir="chart_images"):
    """Generate comparison charts for metrics and save as images

    Args:
        comparison_data: Dictionary containing comparison data
        output_dir: Directory to save chart images

    Returns:
        list: List of successfully generated chart file paths
    """
    chart_files = []

    # Create output directory with error handling
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    except PermissionError as e:
        logger.error(f"Permission denied creating chart output directory '{output_dir}': {e}")
        return chart_files
    except OSError as e:
        logger.error(f"OS error creating chart output directory '{output_dir}': {e}")
        return chart_files

    # Get APM metrics for Author and Publisher only
    apm_data = comparison_data.get("apmMetrics", {})
    host_data = comparison_data.get("hostMetrics", {})

    # APM Charts
    for env, env_data in apm_data.items():
        for role in ["Author", "Publisher"]:
            if role not in env_data:
                continue

            role_data = env_data[role]
            for instance_name, metrics in role_data.items():
                try:
                    # Create APM metrics chart
                    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
                    fig.suptitle(f"{env} - {role} ({instance_name}) - APM Metrics Comparison", fontsize=16, fontweight='bold')

                    metric_names = []
                    pre_values = []
                    post_values = []

                    for metric, data in metrics.items():
                        if isinstance(data.get("pre-deployment"), (int, float)) and isinstance(data.get("post-deployment"), (int, float)):
                            metric_names.append(metric)
                            pre_values.append(data["pre-deployment"])
                            post_values.append(data["post-deployment"])

                    # Plot up to 4 metrics
                    for idx, (ax, metric_name) in enumerate(zip(axes.flat, metric_names[:4])):
                        if idx < len(metric_names):
                            pre_val = pre_values[idx]
                            post_val = post_values[idx]
                            categories = ["Pre", "Post"]
                            values = [pre_val, post_val]
                            colors_bar = ['#95a5a6', '#1abc9c']

                            bars = ax.bar(categories, values, color=colors_bar, alpha=0.7, edgecolor='black', width=0.7)
                            ax.set_ylabel("Value")
                            ax.set_title(f"{metric_name}")

                            # Add value labels on bars
                            for bar, val in zip(bars, values):
                                height = bar.get_height()
                                ax.text(bar.get_x() + bar.get_width()/2., height,
                                       f'{val:.2f}',
                                       ha='center', va='bottom', fontsize=12)

                            ax.grid(axis='y', alpha=0.3)

                    plt.tight_layout()
                    chart_file = os.path.join(output_dir, f"apm_{env}_{role}_{instance_name.replace('/', '_')}.png")
                    plt.savefig(chart_file, dpi=100, bbox_inches='tight')
                    plt.close()
                    chart_files.append(chart_file)
                    logger.info(f"Generated: {chart_file}")
                except (ValueError, OSError, IOError) as e:
                    logger.warning(f"Failed to generate APM chart for {env}-{role}-{instance_name}: {e}")
                    plt.close('all')

    # Host Metrics Charts - Consolidated by metric type
    for env, env_data in host_data.items():
        # Group all metrics across all roles and hosts
        all_metrics = {}

        for role in ["Author", "Publisher"]:
            if role not in env_data:
                continue
            role_data = env_data[role]
            for instance_name, metrics in role_data.items():
                for metric, data in metrics.items():
                    if isinstance(data.get("pre-deployment"), (int, float)) and isinstance(data.get("post-deployment"), (int, float)):
                        if metric not in all_metrics:
                            all_metrics[metric] = []
                        all_metrics[metric].append({
                            "instance": f"{role}/{instance_name}",
                            "pre": data["pre-deployment"],
                            "post": data["post-deployment"]
                        })

        # Create one chart per metric showing all hosts
        for metric_name, hosts_data in all_metrics.items():
            try:
                fig, ax = plt.subplots(figsize=(14, 6))

                instance_names = [h["instance"] for h in hosts_data]
                pre_values = [h["pre"] for h in hosts_data]
                post_values = [h["post"] for h in hosts_data]

                x = range(len(instance_names))
                width = 0.35

                bars1 = ax.bar([i - width/2 for i in x], pre_values, width, label='Pre-Deployment', color='#95a5a6', alpha=0.7, edgecolor='black')
                bars2 = ax.bar([i + width/2 for i in x], post_values, width, label='Post-Deployment', color='#1a80bb', alpha=0.7, edgecolor='black')

                ax.set_xlabel('Host Instance', fontsize=14, fontweight='bold')
                ax.set_ylabel('Percentage (%)', fontsize=14, fontweight='bold')
                ax.set_title(f"{env} - {metric_name}", fontsize=18, fontweight='bold')
                ax.set_xticks(x)
                ax.set_xticklabels(instance_names, rotation=45, ha='right', fontsize=12)
                ax.set_ylim(0, 100)
                ax.legend()
                ax.grid(axis='y', alpha=0.3)

                # Add value labels on bars
                for bars in [bars1, bars2]:
                    for bar in bars:
                        height = bar.get_height()
                        ax.text(bar.get_x() + bar.get_width()/2., height,
                               f'{height:.1f}%',
                               ha='center', va='bottom', fontsize=10)

                plt.tight_layout()
                chart_file = os.path.join(output_dir, f"host_{env}_{metric_name}.png")
                plt.savefig(chart_file, dpi=100, bbox_inches='tight')
                plt.close()
                chart_files.append(chart_file)
                logger.info(f"Generated: {chart_file}")
            except (ValueError, OSError, IOError) as e:
                logger.warning(f"Failed to generate host chart for {env}-{metric_name}: {e}")
                plt.close('all')

    return chart_files

def generate_pdf_report(comparison_data, response_text, output_filename="Deployment_Metrics_Summary.pdf"):
    """Generate PDF report with comparison charts and analysis (matching format_insights.py logic)

    Args:
        comparison_data: Dictionary containing comparison data
        response_text: Text summary from API analysis (HTML with metrics)
        output_filename: Path to output PDF file

    Returns:
        bool: True if PDF generated successfully, False otherwise
    """
    import shutil

    chart_files = []
    
    try:
        # Generate charts first
        chart_files = generate_comparison_charts(comparison_data)

        # Create PDF document
        doc = SimpleDocTemplate(output_filename, pagesize=letter,
                               rightMargin=0.5*inch, leftMargin=0.5*inch,
                               topMargin=0.75*inch, bottomMargin=0.75*inch)

        story = []
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=28,
            textColor=colors.black,
            spaceAfter=12,
            alignment=0
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.black,
            spaceAfter=12,
            spaceBefore=12
        )

        # Title page with summary on same page
        story.append(Paragraph("DeployPulse Report", title_style))
        story.append(Spacer(1, 0.2*inch))

        # Add timestamp
        timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        story.append(Paragraph(f"Generated on: {timestamp_str}", styles['Normal']))
        story.append(Spacer(1, 0.25*inch))

        # AI Summary section
        story.append(Paragraph("AI Summary", heading_style))
        story.append(Spacer(1, 0.1*inch))

        if response_text:
            # Format and add response text
            try:
                formatted_story = format_response_text(response_text)
                story.extend(formatted_story)
            except (ValueError, TypeError, AttributeError) as format_err:
                logger.warning(f"Failed to format response text: {format_err}")
                story.append(Paragraph("Summary data could not be formatted", styles['Normal']))
        else:
            story.append(Paragraph("No summary data available", styles['Normal']))

        # Comparison Charts section
        story.append(PageBreak())
        story.append(Paragraph("Comparison Charts", heading_style))
        story.append(Spacer(1, 0.2*inch))

        # Add all chart images
        host_chart_count = 0
        for chart_file in chart_files:
            if not os.path.exists(chart_file):
                logger.warning(f"Chart file not found: {chart_file}")
                continue

            basename = os.path.basename(chart_file)
            is_host_chart = "host_" in basename
            is_apm_chart = "apm_" in basename

            try:
                if is_apm_chart:
                    # APM charts are larger (2x2 subplots), one per page
                    img = Image(chart_file, width=7*inch, height=5*inch)
                    story.append(img)
                    story.append(PageBreak())
                elif is_host_chart:
                    # Host charts are smaller, fit 2 per page
                    img = Image(chart_file, width=7*inch, height=3*inch)
                    story.append(img)
                    host_chart_count += 1

                    if host_chart_count % 2 == 0:
                        story.append(PageBreak())
                    else:
                        story.append(Spacer(1, 0.5*inch))
                else:
                    # Fallback for any other chart type
                    img = Image(chart_file, width=7*inch, height=3*inch)
                    story.append(img)
                    story.append(Spacer(1, 0.15*inch))
                    story.append(PageBreak())
            except (IOError, OSError) as img_err:
                logger.warning(f"Error adding image {chart_file}: {img_err}")
                continue

        # Build PDF
        try:
            doc.build(story)
            logger.info(f"PDF report generated: {output_filename}")
            return True
        except Exception as pdf_err:
            logger.error(f"Failed to generate PDF: {pdf_err}")
            return False

    except (FileNotFoundError, IOError, OSError) as file_err:
        logger.error(f"File system error in PDF generation: {type(file_err).__name__} - {file_err}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in PDF generation: {type(e).__name__} - {e}")
        return False

    finally:
        # Clean up chart images - guaranteed even on failure
        try:
            import shutil
            if os.path.exists("chart_images"):
                shutil.rmtree("chart_images")
                logger.info("Cleaned up temporary chart files")
        except OSError as cleanup_err:
            logger.warning(f"Failed to clean up chart images: {cleanup_err}")

def main():
    try:
        parser = argparse.ArgumentParser(description='Compare PRE and POST deployment snapshots using deployment ID')
        parser.add_argument('deployment_id', help='Deployment ID (e.g., CHG01250744)')
        args = parser.parse_args()

        deployment_id = args.deployment_id
        logger.info(f"Starting comparison for deployment: {deployment_id}")

        # Read log file to get pre and post snapshot paths
        log_file = os.path.join("logs", f"{deployment_id}.json")

        if not os.path.exists(log_file):
            logger.error(f"Log file not found at {log_file}")
            logger.error(f"Make sure you have run fetch_metrics.py for deployment ID: {deployment_id}")
            return False

        # Load log data with error handling
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                log_data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Log file is corrupted (invalid JSON): {e}")
            return False
        except IOError as e:
            logger.error(f"Could not read log file: {e}")
            return False

        if deployment_id not in log_data:
            logger.error(f"Deployment ID '{deployment_id}' not found in log file")
            logger.error(f"Available deployments: {', '.join(log_data.keys())}")
            return False

        deployment_log = log_data[deployment_id]
        pre_file = deployment_log.get("pre_snapshot")
        post_file = deployment_log.get("post_snapshot")

        if not pre_file or not post_file:
            logger.error(f"Missing snapshot files in log")
            logger.error(f"  Pre-deployment snapshot: {pre_file}")
            logger.error(f"  Post-deployment snapshot: {post_file}")
            logger.error(f"Make sure you have run fetch_metrics.py for both pre-deploy and post-deploy")
            return False

        # Verify files exist
        if not os.path.exists(pre_file):
            logger.error(f"Pre-deployment snapshot file not found at {pre_file}")
            return False

        if not os.path.exists(post_file):
            logger.error(f"Post-deployment snapshot file not found at {post_file}")
            return False

        logger.info(f"Using deployment ID: {deployment_id}")
        logger.info(f"Pre-deployment snapshot: {pre_file}")
        logger.info(f"Post-deployment snapshot: {post_file}")

        # Load snapshot files with error handling
        try:
            pre = load_json_file(pre_file)
        except (FileNotFoundError, json.JSONDecodeError, IOError):
            return False

        try:
            post = load_json_file(post_file)
        except (FileNotFoundError, json.JSONDecodeError, IOError):
            return False

        sections = ["apmMetrics", "hostMetrics"]
        comparison_data = {}

        # Units mapping for metrics
        units_map = {
            "CPU_Usage": "%",
            "Memory_Usage": "%",
            "Disk_Usage": "%",
            "ErrorRate": "%",
            "Apdex": "",
            "ResponseTime": " seconds",
            "Throughput": " request/minute"
        }

        try:
            for section in sections:
                comparison_data[section] = {}
                pre_section = pre.get(section, {})
                post_section = post.get(section, {})
                for env in pre_section.keys():
                    comparison_data[section][env] = {}
                    pre_env = pre_section.get(env, {})
                    post_env = post_section.get(env, {})
                    for role in pre_env.keys():
                        # Only include Author and Publisher roles
                        if role not in ["Author", "Publisher"]:
                            continue
                        comparison_data[section][env][role] = {}
                        pre_role = pre_env.get(role, {})
                        post_role = post_env.get(role, {})
                        for name in pre_role.keys():
                            comparison_data[section][env][role][name] = {}
                            pre_name = pre_role.get(name, {})
                            post_name = post_role.get(name, {})
                            for metric in pre_name.keys():
                                preValRaw = pre_name.get(metric, "N/A")
                                postValRaw = post_name.get(metric, "N/A")

                                unit = units_map.get(metric, "")

                                metric_data = {
                                    "pre-deployment": preValRaw,
                                    "post-deployment": postValRaw,
                                    "unit": unit
                                }

                                if preValRaw != "N/A" and postValRaw != "N/A":
                                    try:
                                        metric_data["pre-deployment"] = float(preValRaw)
                                        metric_data["post-deployment"] = float(postValRaw)
                                    except (ValueError, TypeError):
                                        pass

                                comparison_data[section][env][role][name][metric] = metric_data
        except (KeyError, AttributeError, TypeError) as e:
            logger.error(f"Failed to process comparison data: {e}")
            return False

        # Create folder path and filename
        comparison_dir = os.path.join("database", deployment_id)
        timestamp = datetime.now().strftime('%Y%m%d-%H%M')
        compare_file = os.path.join(comparison_dir, f"comparison-{deployment_id}-{timestamp}.json")

        # Save to file with error handling
        try:
            with open(compare_file, "w", encoding="utf-8") as f:
                json.dump(comparison_data, f, indent=2)
            logger.info(f"Comparison saved to: {compare_file}")
        except IOError as e:
            logger.error(f"Failed to write comparison file: {e}")
            return False

        # Send GET request with JSON file to URL
        response_text = ""

        try:
            # Send the JSON file as binary data
            with open(compare_file, 'rb') as f:
                headers = {"Content-Type": "application/json"}
                try:
                    response = requests.get(AI_ENDPOINT, data=f.read(), headers=headers, verify=False, timeout=30)
                    response.raise_for_status()

                    logger.info(f"GET request sent to: {AI_ENDPOINT}")
                    logger.info(f"File sent: {compare_file}")
                    logger.info(f"Status code: {response.status_code}")

                    # Parse JSON response and extract message field
                    try:
                        response_json = json.loads(response.text)
                        response_text = response_json.get("message", response.text)
                        
                        # Save AI response to file
                        ai_response_file = os.path.join(comparison_dir, f"ai-response-{deployment_id}-{timestamp}.json")
                        try:
                            with open(ai_response_file, "w", encoding="utf-8") as f:
                                json.dump(response_json, f, indent=2)
                            logger.info(f"AI response saved to: {ai_response_file}")
                        except IOError as file_err:
                            logger.warning(f"Failed to save AI response to file: {file_err}")
                    except json.JSONDecodeError as json_err:
                        logger.warning(f"Failed to parse API response as JSON: {json_err}")
                        response_text = response.text
                except requests.exceptions.Timeout:
                    logger.warning("API request timeout. Continuing with PDF generation without API summary")
                    response_text = ""
                except requests.exceptions.ConnectionError as conn_err:
                    logger.warning(f"Connection error to API: {conn_err}. Continuing with PDF generation without API summary")
                    response_text = ""
                except requests.exceptions.HTTPError as http_err:
                    logger.warning(f"API HTTP error: {http_err}. Continuing with PDF generation without API summary")
                    response_text = ""
                except requests.exceptions.RequestException as req_err:
                    logger.warning(f"API request failed: {req_err}. Continuing with PDF generation without API summary")
                    response_text = ""
        except IOError as e:
            logger.warning(f"Could not read comparison file: {e}. Continuing without API summary")
            response_text = ""
        except (ValueError, TypeError) as format_err:
            logger.warning(f"Error processing API response: {format_err}. Continuing with PDF generation without API summary")
            response_text = ""

        # Generate PDF report with summary from API response and comparison charts
        pdf_filename = os.path.join(comparison_dir, f"Deployment-Metrics-Report-{deployment_id}-{timestamp}.pdf")
        if generate_pdf_report(comparison_data, response_text, pdf_filename):
            logger.info(f"Comparison completed successfully for deployment: {deployment_id}")
            return True
        else:
            logger.warning(f"Comparison processing completed but PDF generation failed")
            return False

    except KeyboardInterrupt:
        logger.info("Execution cancelled by user")
        return False
    except (FileNotFoundError, KeyError) as config_err:
        logger.error(f"Configuration or file error: {type(config_err).__name__} - {config_err}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in main execution: {type(e).__name__} - {e}")
        return False

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
        exit(1)
    except Exception as e:
        logger.error(f"FATAL ERROR: {type(e).__name__} - {e}")
        exit(1)
