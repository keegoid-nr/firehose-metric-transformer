# src/otlp_decoder_function/lambda_function.py
import base64
import os
import logging
import time

# These imports will work because they are packaged with the function.
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, StringKeyValue
# Import the necessary Protobuf messages for creating a DoubleSummary
# ValueAtQuantile is a nested type and does not need to be imported separately.
from opentelemetry.proto.metrics.v1.metrics_pb2 import Metric, DoubleSummary, DoubleSummaryDataPoint
from google.protobuf.internal import decoder, encoder

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- Environment Variable Configuration ---
# Read a comma-separated string of function names.
TARGET_FUNCTION_NAMES_STR = os.environ.get('TARGET_FUNCTION_NAMES', '')
# Split the string into a list and strip whitespace from each name.
TARGET_FUNCTION_NAMES = [name.strip() for name in TARGET_FUNCTION_NAMES_STR.split(',') if name.strip()]

ATTRIBUTE_KEY = os.environ.get('ATTRIBUTE_KEY')
ATTRIBUTE_VALUE = os.environ.get('ATTRIBUTE_VALUE')

# Per the AWS OTel 0.7.0 spec, metric dimensions are translated to 'labels'.
FUNCTION_NAME_LABEL_KEY = "FunctionName"


def parse_delimited_stream(data: bytes) -> list:
    """
    Parses a stream of length-prefixed Protobuf messages, as delivered by Firehose.
    """
    messages = []
    position = 0
    while position < len(data):
        msg_len, new_position = decoder._DecodeVarint32(data, position)
        position = new_position
        msg_buf = data[position : position + msg_len]
        position += msg_len
        request = ExportMetricsServiceRequest()
        request.ParseFromString(msg_buf)
        messages.append(request)
    return messages

def create_custom_summary_metric(function_name: str, custom_attrs: dict) -> Metric:
    """
    Creates a new DoubleSummary metric to hold custom metadata, mimicking
    the structure of standard AWS Lambda metrics.
    """
    # Truncate the current time to the second and convert to nanoseconds
    # to match the format of other AWS metrics in the stream.
    current_time_unix_nano = int(time.time()) * 1000000000

    # Create all the labels for the new metric's data point
    labels = [
        StringKeyValue(key="Namespace", value="AWS/Lambda"),
        StringKeyValue(key="MetricName", value="Custom"),
        StringKeyValue(key=FUNCTION_NAME_LABEL_KEY, value=function_name)
    ]
    for key, value in custom_attrs.items():
        labels.append(StringKeyValue(key=key, value=value))

    # Create the quantile values to represent min and max
    # CORRECTED: ValueAtQuantile is a nested type of DoubleSummaryDataPoint
    quantile_values = [
        DoubleSummaryDataPoint.ValueAtQuantile(quantile=0.0, value=1.0), # Min
        DoubleSummaryDataPoint.ValueAtQuantile(quantile=1.0, value=1.0)  # Max
    ]

    # Create the data point for the DoubleSummary metric
    data_point = DoubleSummaryDataPoint(
        labels=labels,
        start_time_unix_nano=current_time_unix_nano,
        time_unix_nano=current_time_unix_nano,
        count=1,
        sum=1.0,
        quantile_values=quantile_values
    )

    # Create and return the full Metric object.
    return Metric(
        name="amazonaws.com/AWS/Lambda/Custom",
        unit="{Count}",
        double_summary=DoubleSummary(data_points=[data_point])
    )

def add_custom_summary_metric(requests: list[ExportMetricsServiceRequest]):
    """
    Finds metrics from target functions and adds a new, separate summary metric
    containing custom attributes, leaving the original metric untouched.
    """
    if not all([TARGET_FUNCTION_NAMES, ATTRIBUTE_KEY, ATTRIBUTE_VALUE]):
        logger.warning("Required environment variables are not set. Skipping.")
        return

    custom_attrs = {ATTRIBUTE_KEY: ATTRIBUTE_VALUE}

    for request in requests:
        for resource_metrics in request.resource_metrics:
            for ilm in resource_metrics.instrumentation_library_metrics:
                # Keep track of which functions in this batch we've already created a metric for
                processed_functions = set()

                new_metrics_to_add = []
                for metric in ilm.metrics:
                    metric_type = metric.WhichOneof('data')
                    if not metric_type:
                        continue
                    metric_data = getattr(metric, metric_type)
                    for dp in metric_data.data_points:
                        for label in dp.labels:
                            # Check if it's a target function and we haven't processed it yet
                            if label.key == FUNCTION_NAME_LABEL_KEY and label.value in TARGET_FUNCTION_NAMES and label.value not in processed_functions:
                                function_name = label.value
                                logger.info(f"MATCH FOUND for '{function_name}'. Creating custom summary metric.")

                                # Create the new metric and add it to our list
                                info_metric = create_custom_summary_metric(function_name, custom_attrs)
                                new_metrics_to_add.append(info_metric)

                                # Mark this function as processed for this batch
                                processed_functions.add(function_name)

                # Add all the new info metrics to the instrumentation library's metric list
                if new_metrics_to_add:
                    ilm.metrics.extend(new_metrics_to_add)

                    # Log the entire resource_metrics object to see its full structure and content.
                    # logger.info(f"PROCESSING resource_metrics:\n{resource_metrics}")

def serialize_requests_to_delimited_stream(requests: list[ExportMetricsServiceRequest]) -> bytes:
    """
    Serializes a list of ExportMetricsServiceRequest objects back into a
    length-prefixed byte stream for Firehose.
    """
    all_serialized = []
    varint_encoder = encoder._VarintEncoder()
    for request in requests:
        serialized_msg = request.SerializeToString()
        encoded_len_pieces = []
        varint_encoder(encoded_len_pieces.append, len(serialized_msg))
        all_serialized.append(b"".join(encoded_len_pieces))
        all_serialized.append(serialized_msg)
    return b"".join(all_serialized)


def handler(event, context):
    """
    Main Lambda handler for AWS Kinesis Firehose transformation.
    """
    output_records = []
    for record in event['records']:
        record_id = record['recordId']
        try:
            payload_bytes = base64.b64decode(record['data'])
            metric_requests = parse_delimited_stream(payload_bytes)

            # Add the new custom metric without modifying existing ones
            add_custom_summary_metric(metric_requests)

            output_payload_bytes = serialize_requests_to_delimited_stream(metric_requests)
            output_records.append({
                'recordId': record_id,
                'result': 'Ok',
                'data': base64.b64encode(output_payload_bytes).decode('utf-8')
            })
        except Exception as e:
            logger.error(f"Processing failed for record {record_id}: {e}", exc_info=True)
            output_records.append({
                'recordId': record_id,
                'result': 'ProcessingFailed',
                'data': record['data']
            })
    logger.info(f"Successfully processed {len(output_records)} records.")
    return {'records': output_records}
