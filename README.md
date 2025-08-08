# AWS Firehose Metric Transformer for CloudWatch Metric Streams

This AWS SAM project deploys a Lambda function designed to act as a transformation layer for an Amazon Kinesis Data Firehose stream. The primary use case is to intercept metrics from an AWS CloudWatch Metric Stream in **OpenTelemetry (OTLP) 0.7.0 Protobuf** format, create a new custom metric with additional attributes for specific resources, and then forward the entire payload to a destination like New Relic.

---

## 🏛️ Architecture

The data flows through the following AWS services:

1. **CloudWatch Metric Stream**: Captures near real-time metrics from your AWS account.
2. **Kinesis Data Firehose**: Receives the metric stream and is configured to use a Lambda function for data transformation.
3. **AWS Lambda Function (This Project)**: The core transformation logic. It decodes each record, inspects it, adds a new custom metric where required, and returns the modified payload to the Firehose stream.
4. **Destination**: The Firehose stream sends the transformed data to its final destination (e.g., New Relic, Datadog, or an S3 bucket).

---

## ✨ Features

* **Custom Metric Creation**: When a metric from a target Lambda function is found, this function creates a new `amazonaws.com/AWS/Lambda/Custom` metric. This new metric contains custom attributes (e.g., `env:dev`) without altering the original AWS metrics. In New Relic, it will show up as `aws.lambda.env` with a value of `dev`.
* **Efficient Protobuf Handling**: Natively decodes, modifies, and re-encodes OTLP Protobuf messages, preserving the efficient binary format throughout the pipeline.
* **Selective Transformation**: Only adds a custom metric for data from a predefined list of target functions. All other metrics are passed through untouched.
* **Serverless & Scalable**: Built with AWS SAM for easy deployment and management of a scalable, serverless architecture.
* **Error Handling**: Safely processes records and returns them to Firehose for retry/backup in case of a processing failure.

### Metric Format

```json
resource {
  attributes {
    key: "cloud.provider"
    value {
      string_value: "aws"
    }
  }
  attributes {
    key: "cloud.account.id"
    value {
      string_value: "123456789123"
    }
  }
  attributes {
    key: "cloud.region"
    value {
      string_value: "us-west-2"
    }
  }
  attributes {
    key: "aws.exporter.arn"
    value {
      string_value: "arn:aws:cloudwatch:us-west-2:123456789123:metric-stream/kmullaney-metric-stream"
    }
  }
}
instrumentation_library_metrics {
  metrics {
    name: "amazonaws.com/AWS/Lambda/Custom"
    unit: "{Count}"
    double_summary {
      data_points {
        labels {
          key: "Namespace"
          value: "AWS/Lambda"
        }
        labels {
          key: "MetricName"
          value: "Custom"
        }
        labels {
          key: "FunctionName"
          value: "kmullaney-sam-python-311-sqs"
        }
        labels {
          key: "env"
          value: "dev"
        }
        start_time_unix_nano: 1754679409000000000
        time_unix_nano: 1754679409000000000
        count: 1
        sum: 1
        quantile_values {
          value: 1
        }
        quantile_values {
          quantile: 1
          value: 1
        }
      }
    }
  }
}
```

---

### ⚠️ Important Note on New Relic Entity Correlation

The custom metric (`amazonaws.com/AWS/Lambda/Custom`) created by this function **will not be automatically associated with a New Relic entity** (i.e., it will not have an `entity.guid`).

Because this is a new, custom metric, it is not processed by New Relic's standard AWS Lambda integration pipeline. As a result, it will not be enriched with the following entity-related attributes that are normally present on standard Lambda metrics:

* `aws.Arn`
* `aws.lambda.functionArn`
* `aws.lambda.functionName`
* `aws.lambda.handler`
* `aws.lambda.memorySize`
* `aws.lambda.role`
* `aws.lambda.runtime`
* `aws.lambda.timeout`
* `displayName`
* `entity.guid`
* `entity.id`
* `entity.name`
* `entity.type`
* `entityName`
* `tags.aws:cloudformation:logical-id`
* `tags.aws:cloudformation:stack-id`
* `tags.aws:cloudformation:stack-name`
* `tags.description`
* `tags.env`
* `tags.lambda:createdBy`
* `tags.owner`
* `tags.reason`

The original AWS metrics (e.g., `aws.lambda.Invocations`) are passed through unmodified and **will** retain their full entity correlation. The custom metric should be used specifically for querying the added attributes alongside the `FunctionName`.

---

## 🛠️ Prerequisites

Before you begin, ensure you have the following tools installed and configured:

* **AWS CLI**: Configured with credentials for your AWS account.
* **AWS SAM CLI**: The primary tool for building and deploying the application.
* **Docker**: Required for building the Lambda deployment package in a container (`--use-container` flag).
* **Python 3.12** and **pip**: For installing project dependencies.

---

## ⚙️ Project Setup

1. **Clone the Repository**:

    ```bash
    git clone <your-repository-url>
    cd <your-repository-directory>
    ```

2. **Build the Application**:
    This command will build the source of your application and create the necessary deployment artifacts.

    ```bash
    sam build --use-container
    ```

3. **Deploy the Application**:
    Deploy the packaged application to your AWS account. SAM will guide you through the parameters.

    ```bash
    sam deploy --guided
    ```

## 🔧 Configuration

The function is configured via parameters in the `template.yaml` file, which are passed as environment variables to the Lambda function during deployment.

* **`TargetFunctionNames`**: (Required) A comma-separated list of Lambda function names whose metrics you want to add attributes to.
* **`AttributeKey`**: (Required) The key for the custom attribute (e.g., `env`).
* **`AttributeValue`**: (Required) The value for the custom attribute (e.g., `dev`).

**Example `template.yaml` section:**

```yaml
Parameters:
  TargetFunctionNames:
    Type: String
    Description: A comma-separated list of Lambda function names to transform metrics for.
  AttributeKey:
    Type: String
    Description: The key for the custom attribute to add (e.g., env).
  AttributeValue:
    Type: String
    Description: The value for the custom attribute to add (e.g., dev).

Resources:
  OtlpDecoderFunction:
    Type: AWS::Serverless::Function
    Properties:
      # ... other properties
      Environment:
        Variables:
          TARGET_FUNCTION_NAMES: !Ref TargetFunctionNames
          ATTRIBUTE_KEY: !Ref AttributeKey
          ATTRIBUTE_VALUE: !Ref AttributeValue
      # ... other properties
