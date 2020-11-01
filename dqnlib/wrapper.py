import gym
import cv2
import gym.spaces
import numpy as np
import collections


class FireResetEnv(gym.Wrapper):
    def __init__(self, env=None):
        super(FireResetEnv, self).__init__(env)
        assert env.unwrapped.get_action_meanings()[1] == 'FIRE'
        assert len(env.unwrapped.get_action_meanings()) >= 3

    def step(self, action):
        return self.env.step(action)

    def reset(self):
        self.env.reset()
        obs, _, is_done, _ = self.env.step(1)
        if is_done:
            self.env.reset()
        obs, _, is_done, _ = self.env.step(2)
        if is_done:
            self.env.reset()
        return obs


class MaxAndSkipEnv(gym.Wrapper):
    def __init__(self, env=None, skip=4):
        super(MaxAndSkipEnv, self).__init__(env)
        self._obs_buffer = collections.deque(maxlen=2)
        self._skip = skip

    def step(self, action):
        is_done = None
        total_reward = 0.0
        for _ in range(self._skip):
            obs, reward, is_done, info = self.env.step(action)
            total_reward += reward
            self._obs_buffer.append(obs)
            if is_done:
                break
        max_frame = np.max(np.stack(self._obs_buffer, axis=0))
        return max_frame, total_reward, is_done, info

    def reset(self):
        self._obs_buffer.clear()
        obs = self.env.reset()
        self._obs_buffer.append(obs)
        return obs


class ProcessFrames84(gym.ObservationWrapper):
    def __init__(self, env=None):
        super(ProcessFrames84, self).__init__(env)
        self.observation_space = gym.spaces.Box(high=255, low=0, shape=(84, 84, 1), dtype=np.uint8)

    def observation(self, observation):
        return ProcessFrames84.process(observation)

    @staticmethod
    def process(frame):
        if frame.size == 210 * 160 * 3:
            img = np.reshape(frame, newshape=[210, 160, 3]).astype(np.float32)
        elif frame.size == 250 * 160 * 3:
            img = np.reshape(frame, newshape=[250, 160, 3]).astype(np.float32)
        else:
            assert False, "Unknown Resolution"
        img = img[:, :, 0] * 0.299 + img[:, :, 1] * 0.587 + img[:, :, 2] * 0.114
        resized_screen = cv2.resize(src=img, dsize=(84, 110), interpolation=cv2.INTER_AREA)
        x_t = resized_screen[18:102, 1]
        x_t = np.reshape(x_t, [84, 84, 1])
        return x_t.astype(np.uint8)


class BufferWrapper(gym.ObservationWrapper):
    def __init__(self, env, n_steps, dtype=np.float32):
        super(BufferWrapper, self).__init__(env)
        self.dtype = dtype
        old_space = env.observation_space
        self.observation_space = gym.spaces.Box(low=old_space.low.repeat(n_steps, axis=0),
                                                high=old_space.high.repeat(n_steps, axis=0),
                                                dtype=dtype)

    def reset(self):
        self.buffer = np.zeros_like(self.observation_space.low, dtype=self.dtype)
        return self.observation(self.env.reset())

    def observation(self, observation):
        self.buffer[:-1] = self.buffer[1:]
        self.buffer[-1] = observation
        return self.buffer


class ImageToPyTorch(gym.ObservationWrapper):
    def __init__(self, env):
        super(ImageToPyTorch, self).__init__(env)
        old_shape = self.observation_space.shape
        new_shape = (old_shape[-1], old_shape[0], old_shape[1])
        self.observation_space = gym.spaces.Box(low=0.0, high=1.0, shape=new_shape, dtype=np.float32)

    def observation(self, observation):
        return np.moveaxis(observation, 2, 0)


class ScaledFloatFrame(gym.ObservationWrapper):
    def observation(self, observation):
        return np.array(observation).astype(np.float32) / 255.0


def make_env(env_name):
    env = gym.make(env_name)
    env = MaxAndSkipEnv(env)
    env = FireResetEnv(env)
    env = ProcessFrames84(env)
    env = ImageToPyTorch(env)
    env = BufferWrapper(env, 4)
    return ScaledFloatFrame(env)
