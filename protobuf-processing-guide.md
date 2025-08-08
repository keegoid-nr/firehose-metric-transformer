# Decoding OTLP 1.0.0: A Definitive Guide to Processing Protobuf Metric Streams with Python 3.12 on AWS Lambda

The landscape of modern observability is rapidly converging on standardized, high-performance telemetry protocols. [cite_start]OpenTelemetry (OTLP) has emerged as the de facto industry standard, offering a unified framework for generating and collecting metrics, logs, and traces. [cite: 2, 3] [cite_start]Within this framework, the use of efficient binary serialization formats like Protocol Buffers (Protobuf) is critical for managing the high-throughput data streams characteristic of cloud-native systems. [cite: 4] [cite_start]This combination promises lower network bandwidth, reduced CPU overhead for serialization/deserialization, and strong, schema-enforced data contracts. [cite: 4]

[cite_start]This report addresses a specific and increasingly common technical challenge: how to reliably receive and process a continuous stream of OTLP 1.0.0 Protobuf-encoded metrics originating from AWS CloudWatch Metric Streams within a serverless, event-driven architecture powered by AWS Lambda. [cite: 5] [cite_start]It provides an expert-level, comprehensive guide to building a robust, scalable, and operationally excellent solution, navigating the nuances of the AWS services involved and the intricacies of the OTLP data format. [cite: 5]

## Architectural Blueprint for Serverless Metric Ingestion

[cite_start]A successful solution requires a precise architectural configuration that leverages the strengths of several AWS services working in concert. [cite: 7] [cite_start]The data does not flow directly from CloudWatch to Lambda; [cite: 8] [cite_start]rather, it is mediated by Amazon Kinesis Data Firehose, which imposes a specific, batch-oriented processing model. [cite: 9]

### The Data Flow: CloudWatch -> Kinesis Data Firehose -> Lambda

[cite_start]The end-to-end pipeline for ingesting and processing OTLP metrics follows a distinct three-stage path, as illustrated in the architectural diagram below. [cite: 11]

* [cite_start]**AWS CloudWatch Metric Streams**: This service acts as the definitive source of metric data. [cite: 12] [cite_start]It is configured to capture metrics from various AWS services in near real-time and forward them to a specified destination. [cite: 13] [cite_start]The foundational choice for this architecture is selecting the OpenTelemetry 1.0.0 output format, which ensures all outgoing data adheres to the stable OTLP specification. [cite: 13]
* [cite_start]**Amazon Kinesis Data Firehose: The Crucial Intermediary**: CloudWatch Metric Streams do not trigger Lambda functions directly. [cite: 14] [cite_start]Instead, they deliver their payloads to a Kinesis Data Firehose delivery stream. [cite: 15] [cite_start]Firehose serves as a fully managed, highly scalable, and resilient service designed to buffer and deliver streaming data. [cite: 15] [cite_start]Its role is not merely transport; it is an active component that batches, transforms, and reliably delivers data. [cite: 16]
* [cite_start]**AWS Lambda: The Transformation Engine**: The Lambda function's role is specifically that of a Firehose Data Transformation function. [cite: 17] [cite_start]Firehose invokes the function with batches of records, and the function is responsible for processing each record and returning a result that conforms to a strict contract defined by the Firehose service. [cite: 17]

### Component Configuration Deep Dive

[cite_start]Correctly configuring each component in this pipeline is paramount for the system to function. [cite: 19] [cite_start]A misconfiguration in any one service can lead to data loss or processing failures. [cite: 20]

* [cite_start]**CloudWatch Metric Stream**: The primary configuration involves setting the output format to OpenTelemetry 1.0.0. [cite: 21] [cite_start]Additionally, one must define which metrics are included in the stream, either by selecting entire AWS namespaces (e.g., AWS/EC2, AWS/Lambda) or by creating fine-grained filters for specific metrics. [cite: 21] [cite_start]The destination must be set to the Kinesis Data Firehose stream created for this purpose. [cite: 21]
* **Kinesis Data Firehose**:
  * [cite_start]**Source and Destination**: The source should be configured as "Direct PUT," as it receives data pushed from the CloudWatch service. [cite: 23]
  * [cite_start]**Data Transformation**: The "Transform source records with AWS Lambda" feature must be enabled, and the target Python 3.12 Lambda function must be specified. [cite: 24]
  * [cite_start]**Buffering**: Firehose buffering settings directly influence cost, latency, and the batch size the Lambda function receives. [cite: 25] [cite_start]Buffering hints can be configured by size (e.g., 1 MB to 128 MB) and by time interval (e.g., 60 to 900 seconds). [cite: 26] [cite_start]The delivery is triggered by whichever threshold is met first. [cite: 26]
  * [cite_start]**Source Record Backup**: It is a recommended best practice to enable source record backup to an Amazon S3 bucket. [cite: 27] [cite_start]This archives the raw, untransformed data, which is invaluable for debugging, reprocessing in case of failures, and maintaining an audit trail. [cite: 27]
* **AWS Lambda Function**:
  * [cite_start]**Runtime**: The function should be configured with the Python 3.12 runtime, as specified. [cite: 29]
  * [cite_start]**Execution Role**: The function requires an IAM role with policies that allow it to be invoked by Firehose and to write logs to CloudWatch. [cite: 30] [cite_start]The `AWSLambdaKinesisExecutionRole` managed policy provides the necessary permissions to read from the stream. [cite: 31, 45]
  * [cite_start]**Timeout**: The function's timeout should be set to a value significantly lower than the Firehose invocation timeout of 5 minutes (e.g., 60 seconds) to allow Firehose to perform automatic retries upon function timeout. [cite: 32]

### The Architectural Implications of Firehose Mediation

[cite_start]The decision by AWS to use Kinesis Data Firehose as the intermediary between CloudWatch Metric Streams and downstream processors is not an arbitrary implementation detail; [cite: 34] [cite_start]it is a fundamental architectural choice that dictates the entire processing model. [cite: 35] [cite_start]This design provides significant resilience and scalability at the cost of imposing a specific, rigid contract on the Lambda function. [cite: 36]

[cite_start]A direct invocation from CloudWatch might imply a simple, single-event processing model. [cite: 37] [cite_start]However, Firehose is explicitly a batching service. [cite: 38] [cite_start]It collects and buffers records based on time or size, meaning the Lambda function will always be invoked with a batch of records, never a single metric update in isolation. [cite: 38] [cite_start]Consequently, the core logic of the Lambda handler must be designed to iterate through an array of records contained within the `event['records']` key. [cite: 39]

[cite_start]Furthermore, the function is not a passive consumer; it is an active participant in a transformation workflow. [cite: 40] [cite_start]For every record it receives, it must return a corresponding result object to Firehose. [cite: 41] [cite_start]This response must include the original `recordId`, a result status (e.g., `Ok`, `Dropped`, or `ProcessingFailed`), and the transformed data payload. [cite: 42] [cite_start]This strict input/output contract enables Firehose's built-in resiliency features, such as automatically retrying records marked as `ProcessingFailed` or routing failed records to a backup S3 location. [cite: 42, 43] [cite_start]Therefore, the developer is not merely writing an event handler but is implementing a specific integration pattern—the "Firehose Transformer"—which offers robustness but requires adherence to its predefined rules. [cite: 44]

| Resource                 | Parameter                                     | Recommended Value                                | Rationale/Notes                                                              |
| :----------------------- | :-------------------------------------------- | :----------------------------------------------- | :--------------------------------------------------------------------------- |
| CloudWatch Metric Stream | Output Format                                 | OpenTelemetry 1.0.0                              | [cite_start]Ensures data is in the correct Protobuf schema for parsing. [cite: 45]      |
|                          | Firehose Destination                          | ARN of the created Firehose stream               | [cite_start]Directs the output of the metric stream to the Firehose buffer. [cite: 45]    |
|                          | IAM Role                                      | A role with `firehose:PutRecordBatch` permissions | [cite_start]Allows CloudWatch to write records into the Kinesis Data Firehose stream. [cite: 45] |
| Kinesis Data Firehose    | Data Transformation                           | "Enabled, pointing to the decoder Lambda ARN"    | [cite_start]Activates the Lambda invocation for each batch of records. [cite: 45]       |
|                          | Buffering Hints                               | "Size: 5 MB, Interval: 300 seconds"              | A starting point balancing latency and cost. [cite_start]Tune based on specific needs. [cite: 45] |
|                          | Source Record Backup                          | "Enabled, pointing to an S3 bucket"              | [cite_start]"Critical for debugging, auditing, and disaster recovery. [cite: 45]"       |
|                          | IAM Role                                      | A role with `lambda:InvokeFunction` permissions  | [cite_start]Allows Firehose to invoke the specified transformation Lambda function. [cite: 45] |
| AWS Lambda               | Runtime                                       | Python 3.12                                      | [cite_start]Matches the user query and supports the latest language features. [cite: 45]  |
|                          | Handler                                       | `lambda_function.handler`                        | [cite_start]The entry point for the function code. [cite: 45]                             |
|                          | Timeout                                       | 60 seconds                                       | [cite_start]Must be less than the Firehose 5-minute timeout to allow for retries. [cite: 45] |
|                          | Execution Role                                | `AWSLambdaKinesisExecutionRole`                  | [cite_start]Provides necessary permissions to read from the stream and write logs. [cite: 45] |
|                          | Layer                                         | `otlp_parser_layer`                              | [cite_start]Provides the opentelemetry-proto and protobuf dependencies. [cite: 45]      |

## Deconstructing the OTLP 1.0.0 Metrics Payload

[cite_start]To decode the data stream, a deep understanding of the OTLP 1.0.0 metrics data model is essential. [cite: 47] [cite_start]This model is defined by a set of Protobuf schemas that act as a strict data contract. [cite: 48]

### The Protobuf Schema: Your Data Contract

[cite_start]Protocol Buffers use `.proto` files to define the structure of data messages in a language-agnostic way. [cite: 50] [cite_start]The OpenTelemetry project maintains all official OTLP `.proto` files in the `open-telemetry/opentelemetry-proto` GitHub repository. [cite: 50]

[cite_start]While it is possible to manually compile these `.proto` files into Python code using the `protoc` compiler, this is not the recommended approach. [cite: 51] [cite_start]The OpenTelemetry community provides the `opentelemetry-proto` package on PyPI, which contains pre-generated Python classes for the entire OTLP data model. [cite: 52] [cite_start]Using this package is the standard, simplest, and most reliable method, as it ensures compatibility and abstracts away the code generation process. [cite: 52]

### Data Model Hierarchy: From Request to Data Point

[cite_start]The metric payload is a deeply nested structure. [cite: 54] [cite_start]Understanding this hierarchy is key to navigating the data in Python code. [cite: 54]

* [cite_start]**`ExportMetricsServiceRequest`**: This is the top-level message defined in the collector service protocol (`metrics_service.proto`). [cite: 55] [cite_start]It acts as a wrapper for a batch of metrics and is the primary object type that will be parsed from the incoming data stream. [cite: 55] [cite_start]It contains a repeated field of `ResourceMetrics`. [cite: 56]
* [cite_start]**`ResourceMetrics`**: This message groups all metrics that originate from a single monitored resource (e.g., one EC2 instance). [cite: 57] [cite_start]It contains a `resource` object and a list of `scope_metrics`. [cite: 58] [cite_start]The resource object itself is a collection of key-value attributes that identify the source, such as `service.name`, `cloud.account.id`, and `cloud.region`. [cite: 58]
* [cite_start]**`ScopeMetrics`**: This message groups metrics generated by a single instrumentation scope or library. [cite: 59] [cite_start]For metrics from CloudWatch Streams, this level is less significant, but it contains the essential list of `Metric` objects. [cite: 60]
* [cite_start]**`Metric`**: This is the core message representing a single metric. [cite: 61] [cite_start]It contains metadata like `name` (e.g., `aws.ec2.cpu_utilization`), `description`, and `unit`. [cite: 62] [cite_start]Crucially, it also contains a oneof data field that holds the actual metric value, which can be one of several types. [cite: 63]
* [cite_start]**Data Point Types**: The OTLP specification defines several kinds of metric data points, including `Sum` (for counters), `Gauge` (for values that can go up and down), and `Histogram` (for distributions). [cite: 64]

### CloudWatch's Opinionated Use of the OTLP Schema

[cite_start]While the OTLP specification is broad, the data from AWS CloudWatch Metric Streams is highly specific and normalized. [cite: 66] [cite_start]CloudWatch does not use the full spectrum of OTLP metric types. [cite: 67] [cite_start]Instead, it maps all CloudWatch metrics—regardless of their original nature—into a single, specific OTLP type: the **Summary data point**. [cite: 68]

[cite_start]This is a non-obvious but critical implementation detail that vastly simplifies the required parsing logic. [cite: 69] [cite_start]A generic OTLP receiver would need to be prepared to handle `Sum`, `Gauge`, `Histogram`, and `Summary` types, requiring complex conditional logic in the code. [cite: 70] [cite_start]However, because the source system (CloudWatch Metric Streams) guarantees that all data will be in the `Summary` format, the Lambda function's code can be written with the direct assumption that the data will always be located in the `metric.summary.data_points` field. [cite: 71] [cite_start]This avoids the need for defensive `HasField` checks and streamlines the entire decoding process, making the solution more efficient and less error-prone for this specific use case. [cite: 72] [cite_start]The developer is shielded from the full complexity of the OTLP spec by the source system's "opinionated" data normalization. [cite: 73]

| Conceptual Field            | OTLP Protobuf Path (Python class access)                                | Example Value/Description                                           |
| :-------------------------- | :---------------------------------------------------------------------- | :-------------------------------------------------------------------- |
| Resource Account ID         | `resource_metrics.resource.attributes['cloud.account.id'].string_value` | `"123456789012"`                                                      |
| Resource Region             | `resource_metrics.resource.attributes['cloud.region'].string_value`     | `"us-east-1"`                                                         |
| Metric Namespace            | Parsed from `metric.name`                                               | `"AWS/EC2"` (from `"aws.ec2.cpu_utilization"`)                        |
| Metric Name                 | Parsed from `metric.name`                                               | `"CPUUtilization"` (from `"aws.ec2.cpu_utilization"`)                 |
| Metric Unit                 | `metric.unit`                                                           | `"Percent"`                                                           |
| Timestamp (end of period)   | `metric.summary.data_points.time_unix_nano`                             | 1672531200000000000 (Unix nanoseconds)                                |
| Statistic (Count)           | `metric.summary.data_points.count`                                      | 1                                                                     |
| Statistic (Sum)             | `metric.summary.data_points.sum`                                        | 15.75                                                                 |
| Statistic (Min)             | `metric.summary.data_points.quantile_values.value`                      | 15.75 (where `quantile_values.quantile` == 0.0)                       |
| Statistic (Max)             | `metric.summary.data_points.quantile_values.value`                      | 15.75 (where `quantile_values.quantile` == 1.0)                       |

## The Firehose-to-Lambda Interface: Event Structure and Payload Framing

[cite_start]The data arrives at the Lambda function within a specific event envelope defined by Kinesis Data Firehose. [cite: 76] [cite_start]The core challenge lies in unpacking this envelope and correctly interpreting the binary payload within. [cite: 77]

### The Firehose Event Model

[cite_start]The Lambda function is invoked with a JSON event payload that contains metadata about the invocation and a list of records to be processed. [cite: 79] [cite_start]The top-level structure includes keys such as `invocationId`, `deliveryStreamArn`, and `region`. [cite: 80] [cite_start]The most important key is `records`, which is an array of record objects. [cite: 80] [cite_start]Each object in this array has the following structure: [cite: 81]

* [cite_start]**`recordId`**: A unique identifier for the record within the current invocation. [cite: 82] [cite_start]This ID must be used in the response to Firehose. [cite: 83]
* [cite_start]**`approximateArrivalTimestamp`**: A Unix timestamp indicating when the record was received by Firehose. [cite: 84]
* [cite_start]**`data`**: The actual data payload. [cite: 85]

### Payload Encapsulation: Base64 and Binary Data

[cite_start]The `data` field within each Firehose record is not raw binary data. [cite: 87] [cite_start]It is a **base64-encoded string**. [cite: 88] [cite_start]This is a standard practice for safely transmitting binary data within JSON payloads. [cite: 88] [cite_start]The first step in processing any record is to decode this string into a raw bytes object, which can be accomplished in Python with a single line of code: [cite: 89]

```python
import base64
decoded_data = base64.b64decode(record['data'])
```

### Parsing the Length-Prefixed Stream

[cite_start]After base64 decoding, the resulting bytes object contains the core Protobuf data. [cite: 93] [cite_start]However, a single `decoded_data` blob from one Firehose record is **not** a single Protobuf message. [cite: 94] [cite_start]For efficiency, Firehose concatenates multiple OTLP payloads into a single binary blob for delivery. [cite: 95]

[cite_start]The Protobuf wire format is not self-delimiting; there is no special character or marker that indicates where one message ends and the next begins. [cite: 96] [cite_start]To solve this, the standard technique of **length-prefix framing** is used. [cite: 96] [cite_start]Before each serialized `ExportMetricsServiceRequest` message, its length is written as a variable-length integer (Varint). [cite: 97] [cite_start]AWS documentation confirms this, specifying that each OTLP data structure is preceded by a header containing an `UnsignedVarInt32` that indicates the message length in bytes. [cite: 97]

[cite_start]This has a profound impact on the parsing logic. [cite: 98] [cite_start]A naive call to `request.ParseFromString(decoded_data)` on the entire byte array will fail or, at best, only parse the first message in the stream. [cite: 98] [cite_start]The only correct way to process this data is to implement a streaming parser. [cite: 99] [cite_start]This parser must operate in a loop: [cite: 100]

1. [cite_start]Read the Varint from the current position in the byte buffer to determine the length of the next message. [cite: 101]
2. [cite_start]Read exactly that number of bytes from the buffer. [cite: 102] [cite_start]This slice of bytes is a complete, single `ExportMetricsServiceRequest` message. [cite: 102]
3. [cite_start]Parse this slice using the Protobuf library. [cite: 103]
4. [cite_start]Advance the position in the buffer and repeat the process until the entire buffer has been consumed. [cite: 104]

[cite_start]Failure to implement this length-prefixed streaming logic is the most common and critical error when processing this type of data stream. [cite: 105]

## Implementing the Python 3.12 Decoder Lambda

[cite_start]This section provides the complete, practical implementation of the Lambda function, including dependency management, core parsing logic, and data extraction. [cite: 107]

### Dependency Management with Lambda Layers

[cite_start]To keep the Lambda deployment package small and manage dependencies cleanly, AWS Lambda Layers are the ideal solution. [cite: 109] [cite_start]The layer will contain the necessary Python packages for Protobuf parsing. [cite: 109]

[cite_start]A step-by-step guide to creating the layer package: [cite: 110]

1. [cite_start]**Create the Directory Structure**: The Lambda runtime for Python expects dependencies to be in a specific path. [cite: 111] [cite_start]Create this structure locally: [cite: 112]

    ```bash
    mkdir -p python/lib/python3.12/site-packages
    ```

2. [cite_start]**Install Dependencies**: Install the required packages directly into the target directory. [cite: 113] [cite_start]The `opentelemetry-proto` package contains the pre-generated OTLP message classes, and `protobuf` is the core library for parsing. [cite: 114]

    ```bash
    pip install opentelemetry-proto protobuf --target python/lib/python3.12/site-packages
    ```

3. [cite_start]**Package the Layer**: Navigate to the top-level directory and create a zip archive of the `python` folder. [cite: 115]

    ```bash
    zip -r otlp_parser_layer.zip python
    ```

4. [cite_start]**Upload the Layer**: In the AWS Lambda console, navigate to "Layers," click "Create layer," provide a name, upload the `otlp_parser_layer.zip` file, and select the Python 3.12 compatible runtime. [cite: 117]

### The Lambda Handler and Initial Processing

[cite_start]The main `lambda_function.py` file orchestrates the entire process, from receiving the event from Firehose to returning the transformed results. [cite: 119] [cite_start]The handler must iterate through the incoming records, decode them, parse the Protobuf content, transform it, and then construct a response that Firehose can understand. [cite: 120] [cite_start]The transformed data sent back to Firehose must also be base64-encoded. [cite: 121]

```python
# lambda_function.py
import base64
import json
import logging

from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from google.protobuf.internal import decoder

# (Helper functions parse_delimited_stream and transform_metric_data will be defined here)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    output_records = []
    for record in event['records']:
        record_id = record['recordId']

        try:
            # 1. Decode the base64 payload from Firehose
            payload_bytes = base64.b64decode(record['data'])

            # 2. Parse the length-delimited stream of Protobuf messages
            metric_requests = parse_delimited_stream(payload_bytes)

            # 3. Transform the metrics into a more usable format (e.g., list of dicts)
            transformed_data = transform_metric_data(metric_requests)

            # 4. Prepare the successful response for Firehose
            output_payload = {
                "source_payload": record['data'], # Optional: include original for debugging
                "metrics": transformed_data
            }

            output_records.append({
                'recordId': record_id,
                'result': 'Ok',
                'data': base64.b64encode(json.dumps(output_payload).encode('utf-8')).decode('utf-8')
            })

        except Exception as e:
            logger.error(f"Processing failed for record {record_id}: {e}", exc_info=True)
            output_records.append({
                'recordId': record_id,
                'result': 'ProcessingFailed',
                'data': record['data'] # Return original data on failure for retry
            })

    logger.info(f"Successfully processed {len(output_records)} records.")
    return {'records': output_records}
```

### Core Logic: Parsing the Length-Prefixed Protobuf Stream

[cite_start]This function is the technical linchpin of the solution. [cite: 130] [cite_start]It implements the streaming parser logic discussed previously. [cite: 130] [cite_start]It uses the `_DecodeVarint32` function from the internal `google.protobuf` library, which is a robust and efficient way to read the length prefixes. [cite: 131]

```python
# Part of lambda_function.py
def parse_delimited_stream(data: bytes) -> list:
    """
    Parses a stream of length-prefixed Protobuf messages.
    """
    messages = []
    position = 0
    while position < len(data):
        # Read the length of the next message from the Varint prefix.
        msg_len, new_position = decoder._DecodeVarint32(data, position)
        position = new_position

        # Extract the exact byte buffer for the message.
        msg_buf = data[position : position + msg_len]
        position += msg_len

        # Parse the buffer into an ExportMetricsServiceRequest object.
        request = ExportMetricsServiceRequest()
        request.ParseFromString(msg_buf)
        messages.append(request)

    return messages
```

### Extracting and Utilizing Metric Data

[cite_start]Once the Protobuf objects are parsed, the final step is to extract the relevant data into a simpler, more usable format, like a list of Python dictionaries. [cite: 138] [cite_start]This function iterates through the nested structure, leveraging the knowledge that all metrics will be of the `Summary` type. [cite: 139]

```python
# Part of lambda_function.py
def transform_metric_data(requests: list) -> list[dict]:
    """
    Transforms a list of ExportMetricsServiceRequest objects into a list of simple dicts.
    """
    all_metrics = []
    for request in requests:
        for resource_metrics in request.resource_metrics:
            resource_attrs = {
                attr.key: attr.value.string_value
                for attr in resource_metrics.resource.attributes
            }
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    for dp in metric.summary.data_points:
                        # Extract dimensions/attributes of the specific data point
                        dimensions = {attr.key: attr.value.string_value for attr in dp.attributes}

                        # CloudWatch SummaryDataPoint stores stats. Min/Max are in quantile_values.
                        min_val = next((qv.value for qv in dp.quantile_values if qv.quantile == 0.0), None)
                        max_val = next((qv.value for qv in dp.quantile_values if qv.quantile == 1.0), None)

                        all_metrics.append({
                            "metric_name": metric.name,
                            "unit": metric.unit,
                            "timestamp_ns": dp.time_unix_nano,
                            "count": dp.count,
                            "sum": dp.sum,
                            "min": min_val,
                            "max": max_val,
                            "dimensions": dimensions,
                            "resource_attributes": resource_attrs,
                        })
    return all_metrics
```

## Deployment and Operational Excellence

[cite_start]Moving from code to a production-ready service requires robust deployment practices, error handling, and performance tuning. [cite: 149]

### Infrastructure as Code (IaC) with AWS SAM

[cite_start]The AWS Serverless Application Model (SAM) provides a streamlined way to define and deploy serverless applications as code. [cite: 151] [cite_start]A `template.yaml` file defines all resources, ensuring repeatable and version-controlled deployments. [cite: 151]

```yaml
# template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: >
  Lambda function to decode OTLP Protobuf metrics from a Kinesis Firehose stream.

Parameters:
  TargetFunctionName:
    Type: String
    Description: The name of the Lambda function to transform metrics.
  AttributeKey:
    Type: String
    Description: The key for the custom attribute to add (e.g., env).
  AttributeValue:
    Type: String
    Description: The value for the custom attribute to add (e.g., dev).

Resources:
  OtlpParserLayer:
    Type: AWS::Serverless::LayerVersion
    Properties:
      LayerName: otlp-parser-layer
      Description: Dependencies for OTLP Protobuf parsing (opentelemetry-proto, protobuf)
      ContentUri: layers/otlp_parser/
      CompatibleRuntimes:
        - python3.12
      LicenseInfo: 'Apache-2.0'
      RetentionPolicy: Retain
    Metadata:
      BuildMethod: python3.12

  OtlpDecoderFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: otlp-metrics-decoder
      Runtime: python3.12
      Handler: lambda_function.handler
      CodeUri: src/otlp_decoder_function/
      MemorySize: 256
      Timeout: 60
      Layers:
        - !Ref OtlpParserLayer
      Policies:
        - AWSLambdaKinesisExecutionRole
      Environment:
        Variables:
          TARGET_FUNCTION_NAME: !Ref TargetFunctionName
          ATTRIBUTE_KEY: !Ref AttributeKey
          ATTRIBUTE_VALUE: !Ref AttributeValue

Outputs:
  FunctionArn:
    Description: "ARN of the OTLP Decoder Lambda Function"
    Value: !GetAtt OtlpDecoderFunction.Arn
```

### Error Handling and Resiliency

[cite_start]The Firehose data transformation model has a built-in mechanism for handling errors. [cite: 157] [cite_start]The `result` field in the Lambda's response for each record dictates Firehose's next action: [cite: 157]

* **`Ok`**: The record was processed successfully. [cite_start]Firehose proceeds. [cite: 158]
* **`Dropped`**: The record is unrecoverable (e.g., malformed data). [cite_start]Firehose discards it and moves on, preventing a "poison pill" message from blocking the pipeline. [cite: 159]
* **`ProcessingFailed`**: A transient error occurred. [cite_start]Firehose will automatically retry invoking the Lambda function with the same record according to its retry policy. [cite: 160]

[cite_start]The provided handler code implements this logic within a `try...except` block, returning `'ProcessingFailed'` on any exception to leverage Firehose's retry capabilities. [cite: 161]

### Performance and Cost Optimization

[cite_start]Two primary levers can be used to tune the pipeline's performance and cost: [cite: 163]

* [cite_start]**Lambda Memory**: Protobuf parsing is a CPU-intensive task. [cite: 164] [cite_start]In AWS Lambda, allocating more memory also allocates proportionally more vCPU power. [cite: 164] [cite_start]Increasing the function's memory (e.g., from 128 MB to 512 MB) can significantly decrease parsing time, which may reduce overall cost if the execution duration savings outweigh the higher memory cost. [cite: 165]
* [cite_start]**Firehose Buffering**: The trade-off here is between latency and cost. [cite: 166] [cite_start]Larger buffer sizes and longer buffer intervals (e.g., 10 MB and 5 minutes) will result in fewer, larger batches sent to Lambda. [cite: 167] [cite_start]This reduces the number of Lambda invocations, lowering costs, but increases the end-to-end latency of the metric data. [cite: 168] [cite_start]Conversely, smaller buffers (e.g., 1 MB and 60 seconds) provide lower latency at the expense of more frequent, and thus more costly, invocations. [cite: 168] [cite_start]The optimal setting depends entirely on the specific requirements of the application consuming the data. [cite: 169]

## Conclusion and Strategic Recommendations

[cite_start]Successfully decoding OTLP 1.0.0 Protobuf metric streams from AWS CloudWatch requires navigating a series of specific technical challenges. [cite: 171] [cite_start]The solution presented in this report addresses each one: it correctly models the CloudWatch-to-Firehose-to-Lambda architecture, handles the base64 encoding of the payload, and, most critically, implements a streaming parser to correctly process the length-prefix-delimited Protobuf messages. [cite: 172]

### Summary of Key Challenges and Solutions

* [cite_start]**Architectural Model**: The pipeline is not a direct trigger but a mediated, batch-oriented flow through Kinesis Data Firehose. [cite: 174] [cite_start]The solution embraces this by designing the Lambda function as a Firehose Transformer, adhering to its specific input/output contract. [cite: 175]
* [cite_start]**Payload Framing**: The primary hurdle is the length-prefixed stream of Protobuf messages. [cite: 176] [cite_start]The solution provides a robust Python function that correctly decodes the stream message by message, avoiding common parsing failures. [cite: 177]
* [cite_start]**Data Model Specificity**: The solution leverages the fact that CloudWatch normalizes all metrics to the OTLP `Summary` type, simplifying the data extraction logic and making the code more efficient for its specific purpose. [cite: 178]

### Pattern Applicability: Custom Parser vs. OTel Collector

[cite_start]The lightweight, custom parsing pattern detailed in this report is highly effective, but it is not a universal solution. [cite: 180] [cite_start]The choice between this pattern and deploying a full OpenTelemetry Collector depends on the complexity of the downstream requirements. [cite: 181]

**Use This Custom Parser Pattern When:**

* [cite_start]The primary goal is simple transformation (e.g., Protobuf-to-JSON), filtering, or routing to a single destination. [cite: 183]
* [cite_start]Low operational overhead and minimal infrastructure are key priorities. [cite: 184]
* [cite_start]Low latency is critical, and the overhead of a collector is undesirable. [cite: 185]

**Use an OpenTelemetry Collector When:**

* [cite_start]Complex processing is required, such as modifying attributes, sampling, or complex batching logic. [cite: 187]
* [cite_start]Telemetry data needs to be fanned out to multiple, heterogeneous backends (e.g., Prometheus, Jaeger, and a vendor platform simultaneously). [cite: 188]
* [cite_start]Advanced resiliency features, such as configurable retry logic with exponential backoff to the final destination, are needed beyond what Firehose provides. [cite: 189]

### Extensibility to Traces and Logs

[cite_start]The fundamental principles and patterns established in this report are directly applicable to processing other OTLP signals. [cite: 191] [cite_start]OTLP traces and logs also use Protobuf and follow the same length-prefix framing when streamed. [cite: 192] [cite_start]A similar Lambda function could be developed to parse `ExportTraceServiceRequest` or `ExportLogsServiceRequest` messages, demonstrating the power and reusability of this architectural pattern for building comprehensive, serverless observability pipelines on AWS. [cite: 193, 194]

### Works Cited

* [196] Python | OpenTelemetry, accessed August 7, 2025, https://opentelemetry.io/docs/languages/python/
* [197] Decoding protobuf messages using AWS Lambda | AWS Compute Blog, accessed August 7, 2025, https://aws.amazon.com/blogs/compute/decoding-protobuf-messages-using-aws-lambda/
* [198] Protocol Buffer Basics: Python, accessed August 7, 2025, https://protobuf.dev/getting-started/pythontutorial/
* [199] Amazon CloudWatch Metric Streams adds support for OpenTelemetry 1.0.0 - AWS, accessed August 7, 2025, https://aws.amazon.com/about-aws/whats-new/2023/12/amazon-cloudwatch-metric-streams-opentelemetry-1-0-0/
* [200] Tutorial: Using Lambda with Kinesis Data Streams - AWS Documentation - Amazon.com, accessed August 7, 2025, https://docs.aws.amazon.com/lambda/latest/dg/with-kinesis-example.html
* [201] CloudWatch metric stream output in OpenTelemetry 1.0.0 format ..., accessed August 7, 2025, https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-metric-streams-formats-opentelemetry-100.html
* [202] Use metric streams - Amazon CloudWatch - AWS Documentation, accessed August 7, 2025, https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Metric-Streams.html
* [203] CloudWatch Metric Streams and Lambda Instrumentation - New Relic Support Forum, accessed August 7, 2025, https://forum.newrelic.com/s/hubtopic/aAX8W0000008biCWAQ/cloudwatch-metric-streams-and-lambda-instrumentation?
* [204] AWS CloudWatch Metrics Integration - Dash0, accessed August 7, 2025, https://www.dash0.com/hub/integrations/int_aws_firehose_cwmetrics/overview
* [205] Amazon Kinesis Firehose Data Transformation with AWS Lambda | AWS Compute Blog, accessed August 7, 2025, https://aws.amazon.com/blogs/compute/amazon-kinesis-firehose-data-transformation-with-aws-lambda/
* [206] Transform source data in Amazon Data Firehose, accessed August 7, 2025, https://docs.aws.amazon.com/firehose/latest/dev/data-transformation.html
* [207] Amazon Kinesis Firehose Data transformation with AWS Lambda | Serverless Land, accessed August 7, 2025, https://serverlessland.com/patterns/firehose-transformation-sam-python
* [208] Building data streaming applications with Amazon Kinesis and serverless - Marcia Villalba, accessed August 7, 2025, https://blog.marcia.dev/building-data-streaming-applications-with-amazon-kinesis-and-serverless
* [209] opentelemetry-proto - PyPI, accessed August 7, 2025, https://pypi.org/project/opentelemetry-proto/
* [210] opentelemetry-exporter-otlp-proto-grpc - PyPI, accessed August 7, 2025, https://pypi.org/project/opentelemetry-exporter-otlp-proto-grpc/
* [211] aws_lambda_powertools.utilities.data_classes.kinesis_firehose_event API documentation - Powertools for AWS, accessed August 7, 2025, https://docs.powertools.aws.dev/lambda/python/2.28.0/api/utilities/data_classes/kinesis_firehose_event.html
* [212] Managing Lambda dependencies with layers - AWS Documentation, accessed August 7, 2025, https://docs.aws.amazon.com/lambda/latest/dg/chapter-layers.html
* [213] Protobuf parsing in Python - Datadog, accessed August 7, 2025, https://www.datadoghq.com/blog/engineering/protobuf-parsing-in-python/
* [214] OpenTelemetry protocol (OTLP) specification and Protobuf definitions - GitHub, accessed August 7, 2025, https://github.com/open-telemetry/opentelemetry-proto
* [215] OpenTelemetry Python Proto - GitHub, accessed August 7, 2025, https://github.com/open-telemetry/opentelemetry-python/blob/main/opentelemetry-proto/README.rst
* [216] opentelemetry-proto/opentelemetry/proto/collector/metrics/v1/metrics_service.proto at main · open-telemetry/opentelemetry-proto - GitHub, accessed August 7, 2025, https://github.com/open-telemetry/opentelemetry-proto/blob/main/opentelemetry/proto/collector/metrics/v1/metrics_service.proto
* [217] Getting Started with the OTLP Exporters | AWS Distro for OpenTelemetry, accessed August 7, 2025, https://aws-otel.github.io/docs/components/otlp-exporter/
* [218] Module: Opentelemetry::Proto::Metrics::V1, accessed August 7, 2025, https://open-telemetry.github.io/opentelemetry-ruby/opentelemetry-exporter-otlp/v0.26.3/Opentelemetry/Proto/Metrics/V1.html
* [219] opentelemetry / opentelemetry.proto.metrics.v1 - Buf, accessed August 7, 2025, https://buf.build/opentelemetry/opentelemetry/docs/main:opentelemetry.proto.metrics.v1
* [220] How can I decode Base64-encoded data in Python using the Base64 module?, accessed August 7, 2025, https://community.lambdatest.com/t/how-can-i-decode-base64-encoded-data-in-python-using-the-base64-module/34907
* [221] Cloudwatch -> Kinesis Firehose -> Lambda Python issue : r/aws - Reddit, accessed August 7, 2025, https://www.reddit.com/r/aws/comments/7pjqfd/cloudwatch_kinesis_firehose_lambda_python_issue/
* [222] How to decrypt data received from kinesis in AWS lambda - Stack Overflow, accessed August 7, 2025, https://stackoverflow.com/questions/70930580/how-to-decrypt-data-received-from-kinesis-in-aws-lambda
* [223] Length-prefix framing for protocol buffers - Eli Bendersky's website, accessed August 7, 2025, https://eli.thegreenplace.net/2011/08/02/length-prefix-framing-for-protocol-buffers
* [224] Encoding | Protocol Buffers Documentation, accessed August 7, 2025, https://protobuf.dev/programming-guides/encoding/
* [225] Creating a Python Lambda Layer As a Zip File | by Macharia Muguku - Medium, accessed August 7, 2025, https://muguku.medium.com/creating-a-python-lambda-layer-as-a-zip-file-72e0e718c0e1
* [226] Working with layers for Python Lambda functions - AWS Documentation, accessed August 7, 2025, https://docs.aws.amazon.com/lambda/latest/dg/python-layers.html
* [227] devel/py-opentelemetry-proto - FreshPorts, accessed August 7, 2025, https://www.freshports.org/devel/py-opentelemetry-proto/
* [228] Collector - OpenTelemetry, accessed August 7, 2025, https://opentelemetry.io/docs/collector/
* [229] Exporters - OpenTelemetry, accessed August 7, 2025, https://opentelemetry.io/docs/languages/python/exporters/
* [230] opentelemetry/proto/collector/trace/v1/trace_service.proto at f5a02da1d7b14c5eb44fd59d22a2c8bd - Buf, accessed August 7, 2025, https://buf.build/opentelemetry/opentelemetry/file/f5a02da1d7b14c5eb44fd59d22a2c8bd:opentelemetry/proto/collector/trace/v1/trace_service.proto
