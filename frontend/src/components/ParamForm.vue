<!--
  ParamForm — 根据后端参数 schema 动态渲染表单。

  - 基础类型 (str/int/float/bool): 渲染对应 Element Plus 控件
  - Pydantic BaseModel: 显示 JSON 编辑框 + 提示有 schema (后续可深入)
  - required 字段加 *, description 显示在下方

  v-model 绑定一个 task_args 对象。
-->
<script setup lang="ts">
import { computed } from 'vue'
import type { TaskParameter } from '@/api/types'

const props = defineProps<{
  parameters: TaskParameter[]
  modelValue: Record<string, any>
}>()
const emit = defineEmits<{ (e: 'update:modelValue', v: Record<string, any>): void }>()

const model = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

function setField(name: string, val: any) {
  emit('update:modelValue', { ...model.value, [name]: val })
}

function isNumeric(t: string) {
  const x = t.toLowerCase()
  return x === 'int' || x === 'integer' || x === 'float' || x === 'number'
}
function isBool(t: string) {
  const x = t.toLowerCase()
  return x === 'bool' || x === 'boolean'
}
</script>

<template>
  <div v-if="!parameters.length" class="empty-hint">该任务无参数</div>
  <el-form v-else label-width="120px" label-position="right">
    <el-form-item
      v-for="p in parameters"
      :key="p.name"
      :label="p.name"
      :required="p.required"
    >
      <!-- Pydantic BaseModel: JSON 编辑 -->
      <template v-if="p.type === 'object' && p.schema">
        <el-input
          type="textarea"
          :rows="4"
          :model-value="typeof model[p.name] === 'string' ? model[p.name] : JSON.stringify(model[p.name] ?? p.default ?? {}, null, 2)"
          placeholder="JSON 对象"
          @update:model-value="(v: any) => setField(p.name, v)"
        />
        <div class="hint">
          模型: <code>{{ p.model_name }}</code>
          (字段见接口文档 /docs)
        </div>
      </template>

      <template v-else-if="isBool(p.type)">
        <el-switch
          :model-value="!!model[p.name]"
          @update:model-value="(v: any) => setField(p.name, v)"
        />
      </template>

      <template v-else-if="isNumeric(p.type)">
        <el-input-number
          :model-value="model[p.name]"
          :placeholder="String(p.default ?? '')"
          style="width:100%"
          @update:model-value="(v: any) => setField(p.name, v)"
        />
      </template>

      <template v-else>
        <el-input
          :model-value="model[p.name]"
          :placeholder="p.description || `类型: ${p.type}`"
          @update:model-value="(v: any) => setField(p.name, v)"
        />
      </template>

      <div v-if="p.description" class="hint">{{ p.description }}</div>
    </el-form-item>
  </el-form>
</template>

<style scoped>
.empty-hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  padding: 8px 0;
}
.hint {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
  margin-top: 4px;
}
</style>
