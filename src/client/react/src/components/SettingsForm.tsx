import { useEffect, useState } from 'react';
import { Form, Input, Select, Switch, Button, Typography, Flex } from 'antd';
import { Link } from 'react-router-dom';
import { CloseOutlined } from '@ant-design/icons';
import validator from '@rjsf/validator-ajv8';

const { Title, Paragraph } = Typography;
const { TextArea } = Input;

import {
    useRTVIClientTransportState,
  } from '@pipecat-ai/client-react';
  

const SettingsForm = ({ schema, onSubmit }) => {
  const transportState = useRTVIClientTransportState();
    

  const [form] = Form.useForm();
  const [isValid, setIsValid] = useState(false);

  const options = schema?.properties?.options?.properties || {};
  const requiredFields = schema?.properties?.options?.required || [];

  // Get top-level name and description
  const schemaName = schema?.properties?.name?.const;
  const schemaDescription = schema?.properties?.description?.const;

  // Extract default values
  const initialValues = Object.entries(options).reduce((acc, [key, def]) => {
    acc[key] = def.default ?? (def.type === 'boolean' ? false : '');
    return acc;
  }, {});

  useEffect(() => {
    form.setFieldsValue({ options: initialValues });
  }, [form, initialValues]);

  const validateSchema = async () => {
    const values = await form.getFieldsValue();
    const result = validator.validateFormData(schema, values);
    setIsValid(result.errors.length === 0);
  };

  const renderFormItem = (key, config) => {
    if (config.const !== undefined) return null; // Skip non-editable fields

    const rules = [];
    if (requiredFields.includes(key)) {
      rules.push({ required: true, message: `${key} is required` });
    }
    if (config.maxLength) {
      rules.push({ max: config.maxLength });
    }

    const label = config.title || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    const namePath = ['options', key];

    if (config.enum) {
      return (
        <Form.Item key={key} name={namePath} label={label} rules={rules}>
          <Select>
            {config.enum.map((val) => (
              <Select.Option key={val} value={val}>
                {val}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
      );
    }

    switch (config.type) {
      case 'boolean':
        return (
          <Form.Item
            key={key}
            name={namePath}
            label={label}
            valuePropName="checked"
            rules={rules}
          >
            <Switch />
          </Form.Item>
        );
      case 'string':
        const multiline = config.maxLength && config.maxLength > 100;
        return (
          <Form.Item key={key} name={namePath} label={label} rules={rules}>
            {multiline ? <TextArea rows={3} /> : <Input />}
          </Form.Item>
        );
      default:
        return null;
    }
  };

  useEffect(() => {
    validateSchema();
  }, []);  

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: 24, position: 'relative' }}>
      {/* Exit Button */}
      <Link to="/" style={{ position: 'absolute', top: 12, right: 12 }}>
        <Button type="text" icon={<CloseOutlined />} />
      </Link>

      {/* Title and Description */}
      <div style={{ marginBottom: 24 }}>
        <Title level={3} style={{ marginBottom: 4 }}>{schemaName}</Title>
        <Paragraph type="secondary" style={{ margin: 0 }}>
          {schemaDescription}
        </Paragraph>
      </div>

      {/* Form */}
      <Form
        form={form}
        layout="vertical"
        onFinish={({ options }) => onSubmit(options)}
        onFieldsChange={validateSchema}
      >
        {Object.entries(options).map(([key, config]) => renderFormItem(key, config))}

        <Form.Item>
            <Button
                type="primary"
                disabled={!isValid || transportState === 'connecting'}
                loading={transportState === 'connecting'}
                onClick={async () => {
                    const values = await form.getFieldsValue();
                    const result = validator.validateFormData(schema, values);
                    if (result.errors.length > 0) return;
                    onSubmit(values.options);
                }}
            >
                Start the session
            </Button>
        </Form.Item>


      </Form>
    </div>
  );
};

export default SettingsForm;
